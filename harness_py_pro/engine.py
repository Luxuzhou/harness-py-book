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
from .plan_state import PlanStateManager
from .plan_tools import (
    UpdatePlanTool, ChecklistWriteTool, ChecklistUpdateTool, ChecklistListTool,
    TaskCreateTool, TaskListTool, TaskUpdateTool, TaskCancelTool,
)
from .subagent_manager import SubAgentManager


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


def _validate_messages(messages: list[dict]) -> list[dict]:
    """
    验证消息序列的合法性，修复 assistant + tool_calls 后缺少 tool 消息的问题。
    返回修复后的消息列表。
    """
    if not messages:
        return messages

    fixed: list[dict] = []
    pending_tool_calls: list[dict] = []

    for i, msg in enumerate(messages):
        if msg.get('role') == 'assistant':
            # 如果有未处理的 tool_calls，先补上假结果
            for tc in pending_tool_calls:
                tc_id = tc.get('id', '')
                tool_name = tc.get('function', {}).get('name', 'unknown')
                fixed.append({
                    'role': 'tool',
                    'tool_call_id': tc_id,
                    'content': f'[message validation - {tool_name} result missing]',
                })
            pending_tool_calls = msg.get('tool_calls', []) or []
            fixed.append(msg)
        elif msg.get('role') == 'tool':
            tc_id = msg.get('tool_call_id', '')
            # 如果 tool_call_id 匹配当前 pending 的某个 tool_call，消费它
            matched = any(tc.get('id') == tc_id for tc in pending_tool_calls)
            if matched:
                pending_tool_calls = [tc for tc in pending_tool_calls if tc.get('id') != tc_id]
            fixed.append(msg)
        else:
            # user / system 消息：如果前面还有未处理的 tool_calls，先补上假结果
            for tc in pending_tool_calls:
                tc_id = tc.get('id', '')
                tool_name = tc.get('function', {}).get('name', 'unknown')
                fixed.append({
                    'role': 'tool',
                    'tool_call_id': tc_id,
                    'content': f'[message validation - {tool_name} result missing]',
                })
            pending_tool_calls = []
            fixed.append(msg)

    # 结尾检查
    for tc in pending_tool_calls:
        tc_id = tc.get('id', '')
        tool_name = tc.get('function', {}).get('name', 'unknown')
        fixed.append({
            'role': 'tool',
            'tool_call_id': tc_id,
            'content': f'[message validation - {tool_name} result missing]',
        })

    return fixed


def _complete_with_client(
    client: object,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> tuple[dict, str | None]:
    messages = _validate_messages(messages)
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

    # 异步子代理管理器（对齐 TUI 的异步子代理模型）
    subagent_mgr = SubAgentManager(
        max_concurrent=10,
        session_dir=ac.cwd / '.harness_sessions' / 'subagents',
    )

    # 子代理 runner：用于 agent_spawn 工具（异步模型）
    def _agent_runner(prompt: str, agent_type: str, allowed_tools: list[str] | None) -> tuple[bool, str]:
        if ac.spawn_depth >= ac.max_spawn_depth:
            return False, f'Sub-agent spawn depth limit reached ({ac.max_spawn_depth})'

        # 根据 agent_type 确定子代理配置（对齐 TUI 类型体系）
        type_tools = {
            'explore': ['read_file', 'grep_search', 'glob_search'],
            'explorer': ['read_file', 'grep_search', 'glob_search'],
            'plan': ['read_file', 'grep_search', 'glob_search', 'write_file'],
            'review': ['read_file', 'grep_search', 'glob_search'],
            'implementer': ['read_file', 'write_file', 'edit_file', 'bash'],
            'implement': ['read_file', 'write_file', 'edit_file', 'bash'],
            'builder': ['read_file', 'write_file', 'edit_file', 'bash'],
            'verifier': ['read_file', 'bash', 'grep_search'],
            'verify': ['read_file', 'bash', 'grep_search'],
            'validator': ['read_file', 'bash', 'grep_search'],
            'tester': ['read_file', 'bash', 'grep_search'],
            'worker': ['read_file', 'write_file', 'edit_file', 'bash', 'grep_search'],
            'general': None,
            'default': None,
            'custom': None,
        }
        # 标准化类型名（处理 TUI 别名）
        normalized_type = {
            'explorer': 'explore',
            'implementer': 'implement',
            'builder': 'implement',
            'verifier': 'verify',
            'validator': 'verify',
            'tester': 'verify',
            'default': 'general',
            'awaiter': 'general',
        }.get(agent_type, agent_type)

        sub_tools = allowed_tools or type_tools.get(agent_type)

        # 写权限：implement/builder/custom 拥有；其他默认只读
        needs_write = normalized_type in ('implement', 'custom')
        # shell 权限：implement/verify/worker/custom 拥有
        needs_shell = normalized_type in ('implement', 'verify', 'worker', 'custom')

        sub_ac = AgentConfig(
            cwd=ac.cwd,
            max_iterations=30,  # 子代理步数限制
            planning_turns=0,
            allow_write=ac.allow_write and needs_write,
            allow_shell=ac.allow_shell and needs_shell,
            tool_filter=sub_tools or [],
            role=f'subagent-{normalized_type}',
            role_prompt=f'You are a sub-agent specialized in {normalized_type}. Work independently and return concise findings.',
            is_subagent=True,
            spawn_depth=ac.spawn_depth + 1,
            max_spawn_depth=ac.max_spawn_depth,
            hooks=ac.hooks,
            sandbox_mode=ac.sandbox_mode,
            network_isolated=ac.network_isolated,
            filesystem_roots=ac.filesystem_roots,
            command_runner=ac.command_runner,
        )

        # 生成唯一 agent_id
        agent_id = f'{ac.role or "root"}-{normalized_type}-{uuid4().hex[:8]}'

        if verbose:
            indent = '  ' * (ac.spawn_depth + 1)
            print(f'{indent}[SUBAGENT] spawn async {agent_type} id={agent_id} depth={ac.spawn_depth + 1}/{ac.max_spawn_depth}')

        # 实际在后台线程运行的子代理逻辑
        def _run_subagent() -> tuple[bool, str]:
            result = run(
                prompt,
                model_config=mc,
                agent_config=sub_ac,
                completion_client=completion_client,
                verbose=verbose,
            )
            summary = (
                f'Sub-agent ({agent_type}) completed.\n'
                f'Steps: {result.turns}, Tools: {result.tool_calls}, Stop: {result.stop_reason}\n'
                f'Output:\n{result.output[:3000]}'
            )
            return True, summary

        # 异步 spawn：立即返回 agent_id，后台线程执行
        subagent_mgr.spawn(agent_id, prompt, agent_type, _run_subagent)

        # 返回 agent_id 给调用者（模型），模型可用 agent_result/agent_wait 查询
        info = (
            f'Sub-agent spawned asynchronously.\n'
            f'agent_id: {agent_id}\n'
            f'type: {agent_type}\n'
            f'status: running\n\n'
            f'CRITICAL: Do NOT read, search, or investigate files that the sub-agent is covering. '
            f'Your next action MUST be `agent_wait({agent_id})` or `agent_result({agent_id})`. '
            f'Do NOT use read_file, grep_search, or glob_search while sub-agents are running.'
        )
        return True, info

    # 规划状态管理器（对齐 TUI 的 Plan + Checklist + Task 体系）
    plan_session_dir = ac.cwd / '.harness_sessions'
    plan_manager = PlanStateManager(plan_session_dir)
    plan_tools = [
        UpdatePlanTool(plan_manager),
        ChecklistWriteTool(plan_manager),
        ChecklistUpdateTool(plan_manager),
        ChecklistListTool(plan_manager),
        TaskCreateTool(plan_manager),
        TaskListTool(plan_manager),
        TaskUpdateTool(plan_manager),
        TaskCancelTool(plan_manager),
    ]

    registry = tool_registry or create_default_registry(
        agent_runner=_agent_runner,
        plan_tools=plan_tools,
        subagent_manager=subagent_mgr,
    )
    hook_executor = HookExecutor(ac.hooks)
    perm_checker = PermissionChecker(ac)
    compressor = Compressor(preserve_messages=ac.compact_preserve_messages)
    guard = LoopGuard()
    budget = TokenBudget.allocate(mc.context_window)
    # AgentConfig.cost_tracker 是生产定制扩展点：用户传入自定义实例（比如对接
    # Prometheus / 自家计费）则替换默认 CostTracker，否则用内置实现。
    cost_tracker = ac.cost_tracker or CostTracker(budget_usd=ac.max_cost_usd)
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

    # 构建system prompt（注入计划状态，对齐 TUI 状态回注）
    plan_context = plan_manager.format_for_prompt()
    system_prompt = build_system_prompt(
        ac.cwd,
        role_prompt=ac.role_prompt,
        extra_context=memory_bundle,
        plan_context=plan_context,
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
                ac.cwd,
                role_prompt=ac.role_prompt,
                extra_context=memory_bundle,
                plan_context=plan_manager.format_for_prompt(),
            )
            if messages and messages[0].get('role') == 'system':
                messages[0]['content'] = new_system

        # === 获取工具schema（阶段限制已移除） ===
        phase_schemas = registry.get_schemas()

        # === 调用LLM ===
        api_start = time.time()
        provider_name = None
        try:
            response, provider_name = _complete_with_client(client, messages, phase_schemas)
        except RuntimeError as exc:
            error_text = str(exc)
            metrics.api_errors += 1
            logger.error('API call failed', error_text)

            # Reactive压缩：仅对上下文长度/token超限类错误触发
            is_context_error = any(kw in error_text.lower() for kw in ('context', 'token', 'length'))
            if is_context_error:
                if verbose:
                    print(f'  [REACTIVE] API上下文报错，紧急压缩')
                before = estimate_tokens(messages, mc.model)
                messages = compressor.compress(
                    messages, int(mc.context_window * 0.5), reactive=True,
                )
                after = estimate_tokens(messages, mc.model)
                metrics.record_compression(before, after)
                logger.compress('reactive', before, after)
                try:
                    response, provider_name = _complete_with_client(client, messages, phase_schemas)
                except RuntimeError as retry_exc:
                    result.stop_reason = f'API error after reactive: {str(retry_exc)[:100]}'
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

        # === 无工具调用 → 检查是否有运行中的子代理（对齐 TUI 自动等待机制） ===
        if not tool_calls_resp:
            running_agents = subagent_mgr.get_running()
            if running_agents:
                if verbose:
                    print(f'  [SUBAGENT] Waiting for {len(running_agents)} sub-agent(s)...')
                for agent_info in running_agents:
                    agent_id = agent_info['agent_id']
                    subagent_mgr.wait(agent_id)
                completed = subagent_mgr.consume_completions()
                if completed:
                    for record in completed:
                        status_label = (
                            'COMPLETED' if record.status.value == 'completed'
                            else record.status.value.upper()
                        )
                        inject_msg = (
                            f'<system-reminder>[SUBAGENT COMPLETE] {record.agent_id}\n'
                            f'Type: {record.agent_type}\n'
                            f'Status: {status_label}\n'
                            f'Duration: {record.to_dict()["duration_sec"]:.1f}s\n'
                            f'Summary:\n{record.result_summary[:2000]}\n'
                            f'Error: {record.error or "none"}'
                            f'</system-reminder>'
                        )
                        messages.append({'role': 'user', 'content': inject_msg})
                        writer.write_event({
                            'type': 'subagent_complete',
                            'agent_id': record.agent_id,
                            'status': record.status.value,
                            'summary': record.result_summary[:500],
                        })
                        if verbose:
                            print(
                                f'  [SUBAGENT] {record.agent_id} {status_label} '
                                f'({record.to_dict()["duration_sec"]:.1f}s)'
                            )
                # 注入结果后继续下一轮，让模型整合子代理发现
                continue

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

        # === Phase 1: Pre-execution LoopGuard (identical-call blocking) ===
        blocked_ids: set[str] = set()
        for tc in tool_calls_resp:
            tool_name = tc.get('function', {}).get('name', '')
            try:
                tool_args = json.loads(tc.get('function', {}).get('arguments', '{}'))
            except json.JSONDecodeError:
                tool_args = {}
            action, guard_msg = guard.check_pre(tool_name, tool_args)
            if action == 'block':
                tc_id = tc.get('id', '')
                blocked_ids.add(tc_id)
                result.tool_calls += 1
                metrics.guard_interventions += 1
                if verbose:
                    print(f'  [GUARD] BLOCK {tool_name}: {guard_msg}')
                # Inject blocked tool result so model knows what happened
                tool_msg = {
                    'role': 'tool',
                    'tool_call_id': tc_id,
                    'content': json.dumps(
                        {'tool': tool_name, 'ok': False, 'content': f'[GUARD BLOCK] {guard_msg}'},
                        ensure_ascii=False,
                    ),
                }
                messages.append(tool_msg)
                writer.write_tool_call(tool_name, tool_args, False, f'[GUARD BLOCK] {guard_msg}')
                writer.write_event({'type': 'loop_guard', 'message': guard_msg})

        # Filter out blocked tools for actual execution
        tool_calls_to_execute = [tc for tc in tool_calls_resp if tc.get('id') not in blocked_ids]

        # === Phase 2: Execute remaining tools (并行或串行) ===
        halt_after_turn = False
        if tool_calls_to_execute:
            if _should_parallelize(tool_calls_to_execute):
                tool_results = _execute_tools_parallel(
                    tool_calls_to_execute, registry, hook_executor, perm_checker, sandbox,
                    ac, iteration, writer, logger, metrics, verbose,
                )
            else:
                tool_results = _execute_tools_sequential(
                    tool_calls_to_execute, registry, hook_executor, perm_checker, sandbox,
                    ac, iteration, writer, logger, metrics, verbose,
                )

            for tc, (ok, tool_content) in zip(tool_calls_to_execute, tool_results):
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

                # Phase 3: Post-execution LoopGuard (failure warn/halt)
                action, guard_msg = guard.check_post(tool_name, ok)
                if action == 'halt':
                    metrics.guard_interventions += 1
                    logger.guard_intervene(guard_msg)
                    if verbose:
                        print(f'  [GUARD] HALT: {guard_msg}')
                    halt_after_turn = True
                    result.stop_reason = f'guard_halt: {guard_msg}'
                elif action == 'warn':
                    metrics.guard_interventions += 1
                    logger.guard_intervene(guard_msg)
                    if verbose:
                        print(f'  [GUARD] WARN: {guard_msg}')
                    # 将 warn 信息嵌入 tool result content，不插入独立 user 消息
                    tool_content += f'\n[LOOP GUARD] {guard_msg}'
                    writer.write_event({'type': 'loop_guard', 'message': guard_msg})

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

        if halt_after_turn:
            break

        # === 如果本回合有 agent_spawn 成功，强制等待子代理完成（防止主代理重复调查）===
        spawn_happened = any(
            tc.get('function', {}).get('name', '') == 'agent_spawn'
            for tc in tool_calls_to_execute
        )
        if spawn_happened:
            running = subagent_mgr.get_running()
            if running:
                if verbose:
                    print(f'  [SUBAGENT] Spawned this turn, waiting for {len(running)} agent(s)...')
                for agent_info in running:
                    subagent_mgr.wait(agent_info['agent_id'])
                completed = subagent_mgr.consume_completions()
                if completed:
                    for record in completed:
                        status_label = 'COMPLETED' if record.status.value == 'completed' else record.status.value.upper()
                        inject_msg = (
                            f'<system-reminder>[SUBAGENT COMPLETE] {record.agent_id}\n'
                            f'Type: {record.agent_type}\n'
                            f'Status: {status_label}\n'
                            f'Duration: {record.to_dict()["duration_sec"]:.1f}s\n'
                            f'Summary:\n{record.result_summary[:2000]}\n'
                            f'Error: {record.error or "none"}'
                            f'</system-reminder>'
                        )
                        messages.append({'role': 'user', 'content': inject_msg})
                        writer.write_event({
                            'type': 'subagent_complete',
                            'agent_id': record.agent_id,
                            'status': record.status.value,
                            'summary': record.result_summary[:500],
                        })
                        if verbose:
                            print(
                                f'  [SUBAGENT] {record.agent_id} {status_label} '
                                f'({record.to_dict()["duration_sec"]:.1f}s)'
                            )

        # === 消费本轮新完成的子代理，将结果注入消息历史（对齐 TUI 的 consume 模型）===
        completed = subagent_mgr.consume_completions()
        if completed:
            for record in completed:
                status_label = 'COMPLETED' if record.status.value == 'completed' else record.status.value.upper()
                inject_msg = (
                    f'<system-reminder>[SUBAGENT COMPLETE] {record.agent_id}\n'
                    f'Type: {record.agent_type}\n'
                    f'Status: {status_label}\n'
                    f'Duration: {record.to_dict()["duration_sec"]:.1f}s\n'
                    f'Summary:\n{record.result_summary[:2000]}\n'
                    f'Error: {record.error or "none"}'
                    f'</system-reminder>'
                )
                messages.append({'role': 'user', 'content': inject_msg})
                writer.write_event({
                    'type': 'subagent_complete',
                    'agent_id': record.agent_id,
                    'status': record.status.value,
                    'summary': record.result_summary[:500],
                })
                if verbose:
                    print(f'  [SUBAGENT] {record.agent_id} {status_label} '
                          f'({record.to_dict()["duration_sec"]:.1f}s)')

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
