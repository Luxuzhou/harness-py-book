"""
核心引擎
========
生产级Agent循环。对标OpenHarness的engine/query.py + harness_py的agent.py。

与教学层的关键区别：
1. 沙箱隔离（进程级网络/文件系统/命令隔离）
2. Hook集成（pre/post tool）
3. 权限检查（路径+工具）
4. 并行工具执行（安全工具并发，危险工具串行）
5. Provider路由与降级
6. CostTracker实时成本追踪
7. Metrics运行时指标
8. 结构化Logger
9. Memory系统集成
10. 支持role_prompt（多Agent场景的角色注入）
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from uuid import uuid4

from .config import ModelConfig, AgentConfig, ensure_utf8_console
from .client import LLMClient
from .tools import create_default_registry, ToolRegistry
from .hooks import HookExecutor
from .permissions import PermissionChecker
from .compact import Compressor
from .loop_guard import LoopGuard
from .prompt import build_system_prompt
from .session import SessionWriter, load_session_messages
from .token_budget import (
    TokenBudget, CostTracker, estimate_tokens, format_budget,
)
from .observe import Logger, Metrics
from .memory import MemoryManager
from .sandbox import Sandbox, create_sandbox


@dataclass
class RunResult:
    """Agent执行结果。"""
    output: str = ''
    turns: int = 0
    tool_calls: int = 0
    total_tokens: int = 0
    stop_reason: str = ''
    session_id: str = ''
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    guard_stats: dict = field(default_factory=dict)
    hook_warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    cost_summary: dict = field(default_factory=dict)


# 只读工具可以安全并行（对标OpenHarness/Hermes的并行策略）
SAFE_PARALLEL_TOOLS = {'read_file', 'grep_search', 'glob_search'}
# 写工具必须串行
NEVER_PARALLEL_TOOLS = {'write_file', 'edit_file', 'bash'}


def _should_parallelize(tool_calls: list[dict]) -> bool:
    """判断工具批次是否可以并行执行。"""
    if len(tool_calls) <= 1:
        return False
    names = {tc.get('function', {}).get('name', '') for tc in tool_calls}
    if names & NEVER_PARALLEL_TOOLS:
        return False
    return names.issubset(SAFE_PARALLEL_TOOLS)


def _complete_with_client(
    client: object,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> tuple[dict, str | None]:
    response = client.complete(messages, tools)  # type: ignore[attr-defined]
    if isinstance(response, tuple):
        if len(response) != 2 or not isinstance(response[0], dict):
            raise TypeError('Completion client returned invalid tuple response')
        provider_name = response[1]
        return response[0], provider_name if isinstance(provider_name, str) else None
    if not isinstance(response, dict):
        raise TypeError('Completion client returned invalid response')
    return response, None


def run(
    task: str,
    *,
    model_config: ModelConfig | None = None,
    agent_config: AgentConfig | None = None,
    tool_registry: ToolRegistry | None = None,
    initial_messages: list[dict] | None = None,
    completion_client: object | None = None,
    verbose: bool = True,
) -> RunResult:
    """
    执行一个任务。harness_py_pro的核心入口。

    支持自定义ToolRegistry（用于多Agent场景的工具过滤）。
    """
    ensure_utf8_console()

    mc = model_config or ModelConfig.from_env()
    ac = agent_config or AgentConfig()

    if not mc.api_key:
        raise ValueError('未设置API key')

    # 初始化组件
    client = completion_client or LLMClient(mc)
    registry = tool_registry or create_default_registry()
    hook_executor = HookExecutor(ac.hooks)
    perm_checker = PermissionChecker(ac)
    compressor = Compressor(preserve_messages=ac.compact_preserve_messages)
    guard = LoopGuard()
    budget = TokenBudget.allocate(mc.context_window)
    cost_tracker = CostTracker(budget_usd=ac.max_cost_usd)
    metrics = Metrics(start_time=time.time())

    # 沙箱
    fs_roots = [ac.cwd / r for r in ac.filesystem_roots] if ac.filesystem_roots else None
    sandbox = create_sandbox(
        ac.cwd,
        mode=ac.sandbox_mode,
        network_isolated=ac.network_isolated,
        allowed_roots=fs_roots,
    )
    ac.command_runner = lambda command, timeout: sandbox.execute_command(command, timeout=timeout)

    session_id = uuid4().hex
    session_dir = ac.cwd / '.harness_sessions'
    writer = SessionWriter(session_id, session_dir, ac.cwd)
    logger = Logger(session_dir, session_id)

    # Memory
    memory_mgr = MemoryManager(ac.cwd)
    memory_bundle = memory_mgr.load_bundle()

    # 构建system prompt
    system_prompt = build_system_prompt(
        ac.cwd,
        role_prompt=ac.role_prompt,
        extra_context=memory_bundle,
    )

    if initial_messages:
        messages = list(initial_messages)
        if messages and messages[0].get('role') == 'system':
            messages[0] = {**messages[0], 'content': system_prompt}
        else:
            messages.insert(0, {'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': task})
    else:
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': task},
        ]

    writer.write_message('system', system_prompt)
    writer.write_message('user', task)
    logger.log('session_start', {
        'model': mc.model,
        'role': ac.role,
        'resumed': bool(initial_messages),
    })

    result = RunResult(session_id=session_id)

    if verbose:
        role_tag = f' role={ac.role}' if ac.role else ''
        print(f'[harness-pro] session={session_id[:12]} model={mc.model}{role_tag}')
        current_est = estimate_tokens(messages, mc.model)
        print(f'[harness-pro] budget={format_budget(budget, current_est)}')

    for iteration in range(1, ac.max_iterations + 1):
        # === 预检压缩 ===
        current_tokens = estimate_tokens(messages, mc.model)
        need, reason = budget.should_compress(current_tokens, ac.compress_threshold_pct)
        if need:
            before = current_tokens
            if verbose:
                print(f'  [COMPRESS] {reason}')

            def llm_summarize(prompt: str) -> str:
                resp, _ = _complete_with_client(client, [{'role': 'user', 'content': prompt}])
                return resp.get('content', '')

            messages = compressor.compress(
                messages, budget.available_for_messages, llm_call=llm_summarize,
            )
            after = estimate_tokens(messages, mc.model)
            metrics.record_compression(before, after)
            logger.compress('preflight', before, after)

            # 压缩后刷新system prompt（对齐Claude Code: Compact Instructions）
            new_system = build_system_prompt(
                ac.cwd, role_prompt=ac.role_prompt, extra_context=memory_bundle,
            )
            if messages and messages[0].get('role') == 'system':
                messages[0]['content'] = new_system

        # === 获取当前phase的工具schema ===
        phase_schemas = registry.get_schemas_for_phase(iteration, ac)

        if verbose and iteration == ac.planning_turns + 1 and ac.planning_turns > 0:
            print(f'  [PHASE] 规划阶段结束，解锁全部工具')

        # === 调用LLM ===
        api_start = time.time()
        provider_name = None
        try:
            response, provider_name = _complete_with_client(client, messages, phase_schemas)
        except RuntimeError as exc:
            error_text = str(exc)
            metrics.api_errors += 1
            logger.error('API call failed', error_text)

            # Reactive压缩
            if any(kw in error_text.lower() for kw in ('context', 'token', '400', 'length')):
                if verbose:
                    print(f'  [REACTIVE] API报错，紧急压缩')
                before = estimate_tokens(messages, mc.model)
                messages = compressor.compress(
                    messages, int(mc.context_window * 0.5), reactive=True,
                )
                after = estimate_tokens(messages, mc.model)
                metrics.record_compression(before, after)
                logger.compress('reactive', before, after)
                try:
                    response, provider_name = _complete_with_client(client, messages, phase_schemas)
                except RuntimeError:
                    result.stop_reason = f'API error after reactive: {error_text[:100]}'
                    break
            else:
                result.stop_reason = f'API error: {error_text[:100]}'
                break
        api_duration = (time.time() - api_start) * 1000
        if provider_name:
            logger.log('provider_select', {'provider': provider_name})

        # 记录usage
        usage = response.get('usage', {})
        input_t = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0)
        output_t = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0)
        result.input_tokens += input_t
        result.output_tokens += output_t
        result.turns = iteration

        metrics.record_api_call(input_t, output_t, api_duration)
        cost_tracker.record(mc.model, input_t, output_t)
        logger.api_call(mc.model, input_t, output_t, api_duration)

        # 成本预算检查
        if cost_tracker.over_budget:
            result.stop_reason = f'cost_budget_exceeded (${cost_tracker.total_cost:.4f})'
            if verbose:
                print(f'  [COST] 超出预算: ${cost_tracker.total_cost:.4f}')
            break

        content = response.get('content', '')
        tool_calls_resp = response.get('tool_calls', [])

        # === 无工具调用 → 自然停止 ===
        if not tool_calls_resp:
            result.output = content or ''
            result.stop_reason = 'stop'
            messages.append({'role': 'assistant', 'content': content})
            writer.write_message('assistant', content)
            break

        # === 记录assistant消息 ===
        messages.append({
            'role': 'assistant',
            'content': content,
            'tool_calls': tool_calls_resp,
        })
        if content:
            writer.write_message('assistant', content)

        # === 执行工具调用（并行或串行） ===
        if _should_parallelize(tool_calls_resp):
            tool_results = _execute_tools_parallel(
                tool_calls_resp, registry, hook_executor, perm_checker, sandbox,
                ac, iteration, writer, logger, metrics, verbose,
            )
        else:
            tool_results = _execute_tools_sequential(
                tool_calls_resp, registry, hook_executor, perm_checker, sandbox,
                ac, iteration, writer, logger, metrics, verbose,
            )

        for tc, (ok, tool_content) in zip(tool_calls_resp, tool_results):
            tool_name = tc.get('function', {}).get('name', '')
            try:
                tc_args = json.loads(tc.get('function', {}).get('arguments', '{}'))
            except json.JSONDecodeError:
                tc_args = {}

            # Post-hook过滤
            if ok:
                post_result = hook_executor.post_tool(tool_name, tc_args, tool_content, ac)
                if post_result.filtered_result:
                    tool_content = post_result.filtered_result
                if post_result.warnings:
                    result.hook_warnings.extend(post_result.warnings)
                    if verbose:
                        for w in post_result.warnings:
                            print(f'  [HOOK] {w}')

            result.tool_calls += 1

            # 构建tool消息
            tool_msg = {
                'role': 'tool',
                'tool_call_id': tc.get('id', ''),
                'content': json.dumps(
                    {'tool': tool_name, 'ok': ok, 'content': tool_content},
                    ensure_ascii=False,
                ),
            }
            messages.append(tool_msg)

            # LoopGuard检查
            try:
                tool_args = json.loads(tc.get('function', {}).get('arguments', '{}'))
            except json.JSONDecodeError:
                tool_args = {}
            intervene, guard_msg = guard.check(tool_name, tool_args, ok, tool_content[:200])
            if intervene:
                metrics.guard_interventions += 1
                logger.guard_intervene(guard_msg)
                if verbose:
                    print(f'  [GUARD] {guard_msg}')
                messages.append({
                    'role': 'user',
                    'content': f'<system-reminder>[LOOP GUARD] {guard_msg}</system-reminder>',
                })
                writer.write_event({'type': 'loop_guard', 'message': guard_msg})

        # 进度日志
        if verbose and iteration % 5 == 0:
            tokens = estimate_tokens(messages, mc.model)
            cost = cost_tracker.total_cost
            print(f'  [Turn {iteration}] msgs={len(messages)} tokens~{tokens:,} '
                  f'tools={result.tool_calls} cost=${cost:.4f}')

    else:
        result.stop_reason = f'max_iterations ({ac.max_iterations})'

    # 完成
    metrics.end_time = time.time()
    result.total_tokens = result.input_tokens + result.output_tokens
    result.cost_usd = cost_tracker.total_cost
    result.guard_stats = guard.stats
    result.metrics = metrics.summary()
    result.cost_summary = cost_tracker.summary()

    writer.close({
        'turns': result.turns,
        'tool_calls': result.tool_calls,
        'total_tokens': result.total_tokens,
        'cost_usd': result.cost_usd,
        'stop_reason': result.stop_reason,
    })
    logger.log('session_end', {
        'turns': result.turns,
        'tool_calls': result.tool_calls,
        'stop_reason': result.stop_reason,
    })

    if verbose:
        print(f'[harness-pro] 完成: turns={result.turns} tools={result.tool_calls} '
              f'tokens={result.total_tokens:,} cost=${result.cost_usd:.4f} stop={result.stop_reason}')
        if result.hook_warnings:
            print(f'[harness-pro] 合规警告: {len(result.hook_warnings)} 条')
        print(metrics.format_report())

    return result


def resume(
    session_id: str,
    prompt: str = 'Please continue the unfinished work.',
    *,
    model_config: ModelConfig | None = None,
    agent_config: AgentConfig | None = None,
    tool_registry: ToolRegistry | None = None,
    completion_client: object | None = None,
    verbose: bool = True,
) -> RunResult:
    ac = agent_config or AgentConfig()
    session_dir = ac.cwd / '.harness_sessions'
    old_messages = load_session_messages(session_id, session_dir)
    if not old_messages:
        raise ValueError(f'Session {session_id} not found or empty')

    return run(
        prompt,
        model_config=model_config,
        agent_config=ac,
        tool_registry=tool_registry,
        initial_messages=old_messages,
        completion_client=completion_client,
        verbose=verbose,
    )


# ============ 工具执行（并行/串行） ============

def _execute_single_tool(
    tc: dict,
    registry: ToolRegistry,
    hook_executor: HookExecutor,
    perm_checker: PermissionChecker,
    sandbox: Sandbox,
    ac: AgentConfig,
    turn: int,
    writer: SessionWriter,
    logger: Logger,
    metrics: Metrics,
    verbose: bool,
) -> tuple[bool, str]:
    """执行单个工具调用（含沙箱+hook+权限三层检查）。"""
    tool_name = tc.get('function', {}).get('name', '')
    try:
        tool_args = json.loads(tc.get('function', {}).get('arguments', '{}'))
    except json.JSONDecodeError:
        tool_args = {}

    tool_start = time.time()
    logger.tool_start(tool_name, tool_args)

    # Layer 3: 沙箱检查（最先，不可绕过）
    sb_ok, sb_reason = sandbox.check_tool_call(tool_name, tool_args)
    if not sb_ok:
        metrics.hook_blocks += 1
        logger.hook_block(tool_name, f'sandbox: {sb_reason}')
        if verbose:
            print(f'  [SANDBOX] 拦截 {tool_name}: {sb_reason}')
        tool_duration = (time.time() - tool_start) * 1000
        metrics.record_tool_call(tool_name, False, tool_duration)
        logger.tool_end(tool_name, False, tool_duration, 0)
        writer.write_tool_call(tool_name, tool_args, False, sb_reason)
        return False, f'[沙箱拦截] {sb_reason}'

    # Layer 2: Pre-hook检查
    hook_result = hook_executor.pre_tool(tool_name, tool_args, ac)
    if not hook_result.allowed:
        metrics.hook_blocks += 1
        logger.hook_block(tool_name, hook_result.reason)
        if verbose:
            print(f'  [HOOK] 拦截 {tool_name}: {hook_result.reason}')
        ok, tool_content = False, f'[HOOK拦截] {hook_result.reason}'
    else:
        tool_ok, tool_reason = perm_checker.check_tool(tool_name)
        if not tool_ok:
            if verbose:
                print(f'  [PERM] 拒绝 {tool_name}: {tool_reason}')
            ok, tool_content = False, f'[权限拒绝] {tool_reason}'
        # 权限检查
        elif tool_args.get('path', ''):
            path_arg = tool_args['path']
            action = 'write' if tool_name in ('write_file', 'edit_file') else 'read'
            perm_ok, perm_reason = perm_checker.check_path(path_arg, action)
            if not perm_ok:
                if verbose:
                    print(f'  [PERM] 拒绝 {tool_name} {path_arg}: {perm_reason}')
                ok, tool_content = False, f'[权限拒绝] {perm_reason}'
            else:
                ok, tool_content = registry.execute_tool(tool_name, tool_args, ac, turn=turn)
        else:
            ok, tool_content = registry.execute_tool(tool_name, tool_args, ac, turn=turn)

    tool_duration = (time.time() - tool_start) * 1000
    metrics.record_tool_call(tool_name, ok, tool_duration)
    logger.tool_end(tool_name, ok, tool_duration, len(tool_content))
    writer.write_tool_call(tool_name, tool_args, ok, tool_content)

    return ok, tool_content


def _execute_tools_sequential(
    tool_calls: list[dict],
    registry: ToolRegistry,
    hook_executor: HookExecutor,
    perm_checker: PermissionChecker,
    sandbox: Sandbox,
    ac: AgentConfig,
    turn: int,
    writer: SessionWriter,
    logger: Logger,
    metrics: Metrics,
    verbose: bool,
) -> list[tuple[bool, str]]:
    """串行执行工具。"""
    results = []
    for tc in tool_calls:
        r = _execute_single_tool(
            tc, registry, hook_executor, perm_checker, sandbox,
            ac, turn, writer, logger, metrics, verbose,
        )
        results.append(r)
    return results


def _execute_tools_parallel(
    tool_calls: list[dict],
    registry: ToolRegistry,
    hook_executor: HookExecutor,
    perm_checker: PermissionChecker,
    sandbox: Sandbox,
    ac: AgentConfig,
    turn: int,
    writer: SessionWriter,
    logger: Logger,
    metrics: Metrics,
    verbose: bool,
) -> list[tuple[bool, str]]:
    """
    并行执行只读工具。对标OpenHarness的concurrent execution。

    只有当所有工具都是安全的只读工具时才并行。
    """
    results: list[tuple[bool, str]] = [None] * len(tool_calls)  # type: ignore

    if verbose and len(tool_calls) > 1:
        names = [tc.get('function', {}).get('name', '') for tc in tool_calls]
        print(f'  [PARALLEL] 并行执行 {len(tool_calls)} 个工具: {names}')

    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 4)) as executor:
        future_to_idx = {}
        for i, tc in enumerate(tool_calls):
            future = executor.submit(
                _execute_single_tool,
                tc, registry, hook_executor, perm_checker, sandbox,
                ac, turn, writer, logger, metrics, verbose,
            )
            future_to_idx[future] = i

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = (False, f'并行执行异常: {e}')

    return results
