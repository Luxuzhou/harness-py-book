"""
多Agent编排
==========
对标OpenHarness的swarm/ + Hermes的delegate_tool。
为Case 3（多Agent全栈开发）提供核心支撑。

设计理念：
- Agent之间通过文件传递信息（不共享内存）
- 每个Agent有独立的对话历史和工具权限
- 编排器控制轮次和终止条件
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import ModelConfig, AgentConfig, HookConfig
from .engine import run, RunResult


@dataclass
class AgentRole:
    """Agent角色定义。"""
    name: str
    role_prompt: str
    tool_filter: list[str] = field(default_factory=list)
    max_iterations: int = 15
    planning_turns: int = 2

    # 角色特有配置
    allow_write: bool = True
    allow_shell: bool = True
    hooks: HookConfig = field(default_factory=HookConfig)


@dataclass
class SwarmResult:
    """多Agent编排结果。"""
    rounds: int = 0
    agents_run: list[dict] = field(default_factory=list)
    final_status: str = ''
    total_tokens: int = 0
    total_tool_calls: int = 0


def orchestrate(
    task: str,
    roles: list[AgentRole],
    *,
    model_config: ModelConfig | None = None,
    cwd: Path | None = None,
    max_rounds: int = 3,
    convergence_check: Any | None = None,
    completion_client: object | None = None,
    verbose: bool = True,
) -> SwarmResult:
    """
    多Agent编排入口。

    流程：
    1. 按roles顺序，每轮依次执行每个Agent
    2. 每个Agent读取前一个Agent的输出文件
    3. 如果convergence_check返回True，提前终止
    4. 最多max_rounds轮

    convergence_check: (round_number, cwd) -> (converged, reason)
    """
    from .config import ModelConfig as MC

    mc = model_config or MC.from_env()
    work_dir = cwd or Path.cwd()
    swarm_result = SwarmResult()

    if verbose:
        print(f'[SWARM] 启动多Agent编排: {len(roles)} 角色, 最多 {max_rounds} 轮')
        for r in roles:
            tools_desc = ', '.join(r.tool_filter) if r.tool_filter else '全部'
            print(f'  - {r.name}: 工具=[{tools_desc}] 迭代上限={r.max_iterations}')

    for round_num in range(1, max_rounds + 1):
        if verbose:
            print(f'\n{"="*50}')
            print(f'[SWARM] 第 {round_num}/{max_rounds} 轮')
            print(f'{"="*50}')

        swarm_result.rounds = round_num

        for role in roles:
            if verbose:
                print(f'\n--- Agent: {role.name} ---')

            # 构建Agent任务（包含原始任务 + 角色指令）
            agent_task = _build_agent_task(task, role, round_num, work_dir)

            # 配置Agent
            agent_config = AgentConfig(
                cwd=work_dir,
                max_iterations=role.max_iterations,
                planning_turns=role.planning_turns,
                allow_write=role.allow_write,
                allow_shell=role.allow_shell,
                role=role.name,
                role_prompt=role.role_prompt,
                tool_filter=role.tool_filter,
                hooks=role.hooks,
            )

            # 执行
            try:
                agent_result = run(
                    agent_task,
                    model_config=mc,
                    agent_config=agent_config,
                    completion_client=completion_client,
                    verbose=verbose,
                )
            except Exception as e:
                agent_result = RunResult(
                    output=f'Agent {role.name} 执行失败: {e}',
                    stop_reason=f'error: {e}',
                )

            swarm_result.agents_run.append({
                'round': round_num,
                'agent': role.name,
                'turns': agent_result.turns,
                'tool_calls': agent_result.tool_calls,
                'tokens': agent_result.total_tokens,
                'stop_reason': agent_result.stop_reason,
            })
            swarm_result.total_tokens += agent_result.total_tokens
            swarm_result.total_tool_calls += agent_result.tool_calls

        # 收敛检查
        if convergence_check:
            try:
                converged, reason = convergence_check(round_num, work_dir)
                if converged:
                    swarm_result.final_status = f'converged: {reason}'
                    if verbose:
                        print(f'\n[SWARM] 收敛: {reason}')
                    break
            except Exception as e:
                if verbose:
                    print(f'[SWARM] 收敛检查异常: {e}')

    else:
        swarm_result.final_status = f'max_rounds ({max_rounds})'

    if verbose:
        print(f'\n[SWARM] 编排完成: {swarm_result.rounds} 轮, '
              f'{swarm_result.total_tool_calls} 工具调用, '
              f'{swarm_result.total_tokens:,} tokens')

    return swarm_result


def _build_agent_task(
    original_task: str,
    role: AgentRole,
    round_num: int,
    work_dir: Path,
) -> str:
    """为Agent构建任务描述。"""
    parts = [f'# 任务\n\n{original_task}']

    if round_num > 1:
        parts.append(f'\n## 当前轮次: 第{round_num}轮\n这不是第一轮执行。请先检查之前轮次的输出文件，了解已有成果和反馈意见。')

    # 检查是否有前序Agent的输出可参考
    output_dir = work_dir / 'output'
    if output_dir.exists():
        existing = [f.name for f in output_dir.iterdir() if f.is_file()]
        if existing:
            parts.append(f'\n## 已有文件\n`output/` 目录下已有: {", ".join(existing[:10])}')

    return '\n'.join(parts)


def run_pipeline(
    stages: list[tuple[str, AgentRole]],
    *,
    model_config: ModelConfig | None = None,
    cwd: Path | None = None,
    completion_client: object | None = None,
    verbose: bool = True,
) -> list[RunResult]:
    """
    顺序流水线执行。每个stage是 (task, role)。
    用于非迭代的顺序多Agent场景。
    """
    mc = model_config or ModelConfig.from_env()
    work_dir = cwd or Path.cwd()
    results = []

    for i, (task, role) in enumerate(stages):
        if verbose:
            print(f'\n--- Pipeline Stage {i+1}/{len(stages)}: {role.name} ---')

        agent_config = AgentConfig(
            cwd=work_dir,
            max_iterations=role.max_iterations,
            planning_turns=role.planning_turns,
            allow_write=role.allow_write,
            allow_shell=role.allow_shell,
            role=role.name,
            role_prompt=role.role_prompt,
            tool_filter=role.tool_filter,
            hooks=role.hooks,
        )

        result = run(
            task,
            model_config=mc,
            agent_config=agent_config,
            completion_client=completion_client,
            verbose=verbose,
        )
        results.append(result)

    return results
