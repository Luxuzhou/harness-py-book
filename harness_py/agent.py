"""
核心Agent循环
=============
全书代码线的主入口。六层架构在此汇聚。
融入Hermes的迭代预算 + 预检压缩 + Claude Code的自然停止。

用法:
    from harness_py import run
    result = run("帮我分析这个项目的代码结构")
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4
from dataclasses import dataclass, field

from .config import ModelConfig, AgentConfig
from .http_client import LLMClient
from .tools import execute_tool, get_schemas_for_phase
from .compressor import Compressor
from .loop_guard import LoopGuard
from .token_budget import TokenBudget, should_compress, format_budget
from .prompt import build_system_prompt
from .memory import load_memory_bundle
from .session import SessionWriter, load_session_messages

log = logging.getLogger('harness_py')


@dataclass
class RunResult:
    """Agent执行结果。"""
    output: str = ''
    turns: int = 0
    tool_calls: int = 0
    total_tokens: int = 0
    stop_reason: str = ''
    session_id: str = ''
    cost_summary: dict = field(default_factory=dict)


def _build_full_system(cwd: Path) -> str:
    """构建完整system prompt（CLAUDE.md + Memory）。唯一组装点。"""
    prompt = build_system_prompt(cwd)
    memory = load_memory_bundle(cwd)
    return prompt + ('\n' + memory if memory else '')


def _ensure_utf8() -> None:
    """确保Windows控制台使用UTF-8。从config.py移入，因为是运行时副作用。"""
    import sys
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def run(
    task: str,
    *,
    model_config: ModelConfig | None = None,
    agent_config: AgentConfig | None = None,
    cost_tracker: Any = None,
    initial_messages: list[dict] | None = None,
) -> RunResult:
    """
    执行一个任务。这是全书代码线的核心函数。

    cost_tracker: 可选的外部成本追踪器，需有 record(key, value) 方法。
    initial_messages: 可选的初始消息列表（用于resume场景）。
    """
    _ensure_utf8()

    mc = model_config or ModelConfig.from_env()
    ac = agent_config or AgentConfig()

    if not mc.api_key:
        raise ValueError('未设置API key。请设置 HARNESS_API_KEY 或 OPENAI_API_KEY 环境变量。')

    client = LLMClient(mc)
    compressor = Compressor(preserve_messages=ac.compact_preserve_messages)
    guard = LoopGuard()
    budget = TokenBudget.allocate(mc.context_window)
    session_id = uuid4().hex
    session_dir = ac.cwd / '.harness_sessions'
    writer = SessionWriter(session_id, session_dir, ac.cwd)

    # 构建消息列表
    if initial_messages:
        messages: list[dict] = list(initial_messages)
        # resume场景：刷新system prompt（CLAUDE.md和日期可能已变化）
        fresh_system = _build_full_system(ac.cwd)
        if messages and messages[0].get('role') == 'system':
            messages[0]['content'] = fresh_system
        messages.append({'role': 'user', 'content': task})
    else:
        system_prompt = _build_full_system(ac.cwd)
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': task},
        ]
        writer.write_message('system', system_prompt)

    writer.write_message('user', task)

    result = RunResult(session_id=session_id)
    total_input_tokens = 0
    total_output_tokens = 0

    log.info(f'session={session_id[:12]} model={mc.model}')
    log.info(f'budget={format_budget(budget, 0)}')

    for iteration in range(1, ac.max_iterations + 1):
        # === 预检压缩 ===
        current_tokens = compressor.total_tokens(messages)
        need, reason = should_compress(budget, current_tokens, ac.compress_threshold_pct)
        if need:
            threshold = int(mc.context_window * ac.compress_threshold_pct)
            log.info(f'[COMPRESS] {reason}')

            def llm_summarize(prompt: str) -> str:
                resp = client.complete([{'role': 'user', 'content': prompt}])
                return resp.get('content', '')

            messages = compressor.compress(messages, threshold, llm_call=llm_summarize)
            if messages and messages[0].get('role') == 'system':
                messages[0]['content'] = _build_full_system(ac.cwd)

        # === 分阶段工具解锁 ===
        phase_schemas = get_schemas_for_phase(iteration, ac)
        if iteration == ac.planning_turns + 1:
            log.info('规划阶段结束，解锁全部工具')

        # === 调用LLM ===
        try:
            response = client.complete(messages, phase_schemas)
        except RuntimeError as exc:
            error_text = str(exc)
            if 'context' in error_text.lower() or 'token' in error_text.lower() or '400' in error_text:
                log.warning(f'API报错，紧急压缩后重试')
                messages = compressor.compress(messages, int(mc.context_window * 0.5), reactive=True)
                try:
                    response = client.complete(messages, phase_schemas)
                except RuntimeError:
                    result.stop_reason = f'API error after reactive: {error_text[:100]}'
                    break
            else:
                result.stop_reason = f'API error: {error_text[:100]}'
                break

        # 记录usage
        usage = response.get('usage', {})
        input_tokens = usage.get('prompt_tokens', 0) or usage.get('input_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0) or usage.get('output_tokens', 0)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        if cost_tracker and hasattr(cost_tracker, 'record'):
            cost_tracker.record(f"{mc.model}_input", input_tokens)
            cost_tracker.record(f"{mc.model}_output", output_tokens)

        result.turns = iteration
        content = response.get('content', '')
        tool_calls = response.get('tool_calls', [])

        # === 无工具调用 → 自然停止 ===
        if not tool_calls:
            result.output = content or ''
            result.stop_reason = 'stop'
            messages.append({'role': 'assistant', 'content': content})
            writer.write_message('assistant', content)
            break

        # === 执行工具调用 ===
        messages.append({
            'role': 'assistant',
            'content': content,
            'tool_calls': tool_calls,
        })
        writer.write_message('assistant', content)

        for tc in tool_calls:
            tool_name = tc.get('function', {}).get('name', '')
            raw_args = tc.get('function', {}).get('arguments', '{}')
            try:
                tool_args = json.loads(raw_args)
            except json.JSONDecodeError:
                ok, tool_content = False, f'Invalid JSON arguments: {raw_args[:200]}'
                tool_args = {}
            else:
                ok, tool_content = execute_tool(tool_name, tool_args, ac, turn=iteration)
            result.tool_calls += 1

            tool_msg = {
                'role': 'tool',
                'tool_call_id': tc.get('id', ''),
                'content': json.dumps({'tool': tool_name, 'ok': ok, 'content': tool_content}, ensure_ascii=False),
            }
            messages.append(tool_msg)
            writer.write_message('tool', tool_msg['content'])

            intervene, guard_msg = guard.check(tool_name, tool_args, ok, tool_content[:200])
            if intervene:
                log.warning(f'[GUARD] {guard_msg}')
                messages.append({'role': 'user', 'content': f'<system-reminder>[LOOP GUARD] {guard_msg}</system-reminder>'})
                writer.write_event({'type': 'loop_guard', 'message': guard_msg})

        if iteration % 5 == 0:
            current_tokens = compressor.total_tokens(messages)
            log.info(f'[Turn {iteration}] msgs={len(messages)} tokens~{current_tokens:,} tools={result.tool_calls}')

    else:
        result.stop_reason = f'max_iterations ({ac.max_iterations})'

    result.total_tokens = total_input_tokens + total_output_tokens
    if cost_tracker and hasattr(cost_tracker, 'summary'):
        result.cost_summary = cost_tracker.summary()
    log.info(f'完成: turns={result.turns} tools={result.tool_calls} tokens={result.total_tokens:,} stop={result.stop_reason}')
    return result


def resume(
    session_id: str,
    prompt: str = '请继续之前未完成的工作。',
    *,
    model_config: ModelConfig | None = None,
    agent_config: AgentConfig | None = None,
    cost_tracker: Any = None,
) -> RunResult:
    """从上次中断的session接续执行。加载历史消息作为初始上下文。"""
    ac = agent_config or AgentConfig()
    session_dir = ac.cwd / '.harness_sessions'
    old_messages = load_session_messages(session_id, session_dir)

    if not old_messages:
        raise ValueError(f'Session {session_id} not found or empty')

    log.info(f'Resume session {session_id[:12]}... ({len(old_messages)} messages)')

    return run(
        prompt,
        model_config=model_config,
        agent_config=ac,
        cost_tracker=cost_tracker,
        initial_messages=old_messages,
    )
