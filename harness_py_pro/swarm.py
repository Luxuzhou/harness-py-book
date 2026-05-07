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
    max_iterations: int = 100
    planning_turns: int = 0  # 0 = 禁用自动阶段切换

    # 角色特有配置
    allow_write: bool = True
    allow_shell: bool = True
    hooks: HookConfig = field(default_factory=HookConfig)

    # 跨项目多Agent场景：覆盖 orchestrate() 的全局 cwd，
    # 让该角色在自己的代码库根目录下执行。
    cwd: Path | None = None

    # 文件系统隔离额外根目录（相对 cwd 的路径）。
    # 默认沙箱只允许访问 cwd 内文件；若角色需要跨目录读取（如 Architect
    # 需同时看 Java 和 Python 两个项目），可在此列出额外根。
    filesystem_roots: list[str] = field(default_factory=list)


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
    parallel_groups: dict[int, list[str]] | None = None,
) -> SwarmResult:
    """
    多Agent编排入口。

    流程：
    1. 按roles顺序，每轮依次执行每个Agent
    2. 每个Agent读取前一个Agent的输出文件
    3. 如果convergence_check返回True，提前终止
    4. 最多max_rounds轮

    convergence_check: (round_number, cwd) -> (converged, reason)

    parallel_groups: {round_number: [role_name, ...]}
        在对应轮次里，这些角色被视为"语义并行"：它们看到的前序产出
        不包含同组其他角色在当轮的输出。执行仍按 roles 顺序串行调用，
        但当轮组内角色互相隔离视角，等价于"多人同时动手"。
        例如 {2: ['JavaDeveloper', 'PythonDeveloper']} 表示第2轮
        Java 和 Python 开发者并行工作、互不等待。
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

        # 计算本轮的并行组（角色名集合）。同组角色互不可见对方当轮输出。
        parallel_names: set[str] = set()
        if parallel_groups and round_num in parallel_groups:
            parallel_names = set(parallel_groups[round_num])
            if verbose and parallel_names:
                print(f'[SWARM] 本轮并行组: {sorted(parallel_names)}')

        # 记录本轮各角色产出（用于下一个角色的 _build_agent_task 可见性判断）
        round_outputs: dict[str, str] = {}

        for role in roles:
            if verbose:
                print(f'\n--- Agent: {role.name} ---')

            # 该角色在本轮能看到的"已产出内容"：
            # 若自己在并行组里，屏蔽组内其他角色的当轮输出。
            visible_round_outputs = {
                n: o for n, o in round_outputs.items()
                if not (role.name in parallel_names and n in parallel_names)
            }

            # 角色各自的工作目录：优先用 role.cwd，否则全局 cwd
            role_cwd = role.cwd or work_dir

            # 构建Agent任务（包含原始任务 + 角色指令 + 可见前序产出）
            agent_task = _build_agent_task(
                task, role, round_num, role_cwd,
                visible_round_outputs=visible_round_outputs,
            )

            # 配置Agent
            agent_config = AgentConfig(
                cwd=role_cwd,
                max_iterations=role.max_iterations,
                planning_turns=role.planning_turns,
                allow_write=role.allow_write,
                allow_shell=role.allow_shell,
                role=role.name,
                role_prompt=role.role_prompt,
                tool_filter=role.tool_filter,
                hooks=role.hooks,
                filesystem_roots=role.filesystem_roots,
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
                'cwd': str(role_cwd),
            })
            swarm_result.total_tokens += agent_result.total_tokens
            swarm_result.total_tool_calls += agent_result.tool_calls

            # 记录本角色的产出，供同轮后续非并行角色参考
            round_outputs[role.name] = agent_result.output or ''

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
    visible_round_outputs: dict[str, str] | None = None,
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

    # 本轮前序角色的输出摘要（若处于并行组中，上游同组角色会被屏蔽）
    if visible_round_outputs:
        summary_lines = []
        for n, out in visible_round_outputs.items():
            snippet = (out or '').strip().splitlines()
            head = '\n'.join(snippet[:6])
            summary_lines.append(f'### 来自 {n} 的产出摘要\n{head}')
        if summary_lines:
            parts.append('\n## 本轮前序角色输出（供参考，不包含与本角色并行的角色）\n' + '\n\n'.join(summary_lines))

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

        stage_cwd = role.cwd or work_dir
        agent_config = AgentConfig(
            cwd=stage_cwd,
            max_iterations=role.max_iterations,
            planning_turns=role.planning_turns,
            allow_write=role.allow_write,
            allow_shell=role.allow_shell,
            role=role.name,
            role_prompt=role.role_prompt,
            tool_filter=role.tool_filter,
            hooks=role.hooks,
            filesystem_roots=role.filesystem_roots,
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
