"""
Ch10 案例：跨 Java / Python 真实业务代码的多 Agent 编排。

本案例**不自建业务代码**。它直接把：
- Java 后端：`cases/refactor_enterprise/target_project/`（Ch8 的 Spring Boot 项目）
- Python 后端：`cases/data_compliance/target_service/`（Ch9 的 FastAPI 合规服务）

作为两个 Developer 角色的真实工作目录，由 Harness 的 orchestrate() 协调：
- Architect 统筹读取两边 spec 并输出 implementation_plan.md
- JavaDeveloper   在 Ch8 的 target_project 里工作（cwd 指向 Java 项目根）
- PythonDeveloper 在 Ch9 的 target_service 里工作（cwd 指向 Python 项目根）
- QAEngineer      回到编排目录产出跨项目契约一致性测试报告

这也是"单 Agent 上下文装不下整套业务"时为什么必须上多 Agent 的真实动因。

用法：
    python cases/multiagent_enterprise/run.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

env_file = REPO_ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())


def _load_ch8_ch9_anchors() -> tuple[Path, Path]:
    """定位 Ch8 Java 项目与 Ch9 Python 服务的根目录。"""
    ch8 = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
    ch9 = REPO_ROOT / 'cases' / 'data_compliance' / 'target_service'
    if not ch8.exists():
        raise FileNotFoundError(
            f'Ch8 Java 项目目录不存在: {ch8}. '
            f'请先确认 cases/refactor_enterprise 已就位。')
    if not ch9.exists():
        raise FileNotFoundError(
            f'Ch9 Python 服务目录不存在: {ch9}. '
            f'请先确认 cases/data_compliance 已就位。')
    return ch8, ch9


def _build_context_block(ch8_root: Path, ch9_root: Path) -> str:
    """把需求、契约、架构、Ch8/Ch9 的定位拼成共享上下文。"""
    requirement = (CASE_DIR / 'spec' / 'requirement.md').read_text(encoding='utf-8')
    architecture = (CASE_DIR / 'spec' / 'architecture.md').read_text(encoding='utf-8')
    api_contract = (CASE_DIR / 'spec' / 'api_contract.yaml').read_text(encoding='utf-8')

    context = f"""
---
## 目标系统定位

本任务在两个真实业务代码库上同时进行：
- **Java 端**（Ch8 案例）：`{ch8_root}`
  完整的临床路径管理 Spring Boot 项目，72 文件 / ~7,929 行。
- **Python 端**（Ch9 案例）：`{ch9_root}`
  临床数据合规 FastAPI 服务，~15,000 行。

JavaDeveloper 的工作目录被 Harness 固定在上面的 Java 根目录。
PythonDeveloper 的工作目录被 Harness 固定在上面的 Python 根目录。
**两个 Developer 互不能改对方的代码**（由 cwd 隔离 + 工具权限保证）。

## 需求规格
{requirement}

## 接口契约
```yaml
{api_contract}
```

## 现有架构
{architecture}
---
"""
    return context


def _build_roles(ch8_root: Path, ch9_root: Path):
    from harness_py_pro.swarm import AgentRole

    architect_prompt = (CASE_DIR / 'roles' / 'architect.md').read_text(encoding='utf-8')
    java_dev_prompt = (CASE_DIR / 'roles' / 'java_developer.md').read_text(encoding='utf-8')
    python_dev_prompt = (CASE_DIR / 'roles' / 'python_developer.md').read_text(encoding='utf-8')
    qa_prompt = (CASE_DIR / 'roles' / 'qa_engineer.md').read_text(encoding='utf-8')

    context_block = _build_context_block(ch8_root, ch9_root)

    PLAN_TOOLS = [
        'update_plan', 'checklist_write', 'checklist_update', 'checklist_list',
        'task_create', 'task_list', 'task_update', 'task_cancel',
    ]
    SUBAGENT_TOOLS = ['agent_spawn', 'agent_result', 'agent_wait', 'agent_cancel', 'agent_list']

    return [
        # Round 1：Architect 统揽 Ch8 + Ch9，产出 implementation_plan.md
        AgentRole(
            name='Architect',
            role_prompt=architect_prompt + context_block,
            tool_filter=['read_file', 'grep_search', 'glob_search', 'write_file'] + SUBAGENT_TOOLS + PLAN_TOOLS,
            max_iterations=30,
            planning_turns=0,
            allow_shell=False,
            cwd=CASE_DIR,  # 只能改编排目录下的 implementation_plan.md
            filesystem_roots=['..', '../..'],
        ),
        # Round 2a：JavaDeveloper 在 Ch8 项目里工作
        AgentRole(
            name='JavaDeveloper',
            role_prompt=java_dev_prompt + context_block,
            tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search', 'glob_search'] + SUBAGENT_TOOLS + PLAN_TOOLS,
            max_iterations=50,
            planning_turns=0,
            cwd=ch8_root,
        ),
        # Round 2b：PythonDeveloper 在 Ch9 项目里工作（与 Java 并行）
        AgentRole(
            name='PythonDeveloper',
            role_prompt=python_dev_prompt + context_block,
            tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search', 'glob_search'] + SUBAGENT_TOOLS + PLAN_TOOLS,
            max_iterations=50,
            planning_turns=0,
            cwd=ch9_root,
        ),
        # Round 3：QAEngineer 回到编排目录做跨项目契约校验
        AgentRole(
            name='QAEngineer',
            role_prompt=qa_prompt + context_block,
            tool_filter=['read_file', 'write_file', 'edit_file', 'bash',
                         'grep_search', 'glob_search'] + SUBAGENT_TOOLS + PLAN_TOOLS,
            max_iterations=30,
            planning_turns=0,
            allow_write=True,
            cwd=CASE_DIR,
            filesystem_roots=['..', '../..'],
        ),
    ]


def convergence_check(round_num, work_dir):
    """收敛条件：test_report.md 存在且没有失败项。"""
    report_file = work_dir / 'test_report.md'
    if not report_file.exists():
        return False, 'test_report.md 尚未生成'
    content = report_file.read_text(encoding='utf-8')
    fail_match = re.search(r'(?:失败|Failed)[：:]\s*(\d+)', content)
    if fail_match:
        fail_count = int(fail_match.group(1))
        if fail_count == 0:
            return True, '所有测试通过，无失败项'
        return False, f'仍有 {fail_count} 个测试失败'
    if 'ALL PASS' in content.upper() or '全部通过' in content:
        return True, '测试报告标记为全部通过'
    return False, '无法判断测试状态'


def main():
    from harness_py_pro import ModelConfig
    from harness_py_pro.swarm import orchestrate

    ch8_root, ch9_root = _load_ch8_ch9_anchors()

    print('=' * 60)
    print('Ch10: 跨 Java + Python 真实业务代码的多 Agent 编排')
    print('=' * 60)
    print(f'编排目录:  {CASE_DIR}')
    print(f'Java 端 cwd (Ch8): {ch8_root}')
    print(f'Python 端 cwd (Ch9): {ch9_root}')
    print()

    task = (CASE_DIR / 'TASK.md').read_text(encoding='utf-8')
    roles = _build_roles(ch8_root, ch9_root)

    result = orchestrate(
        task,
        roles,
        model_config=ModelConfig.from_env(),
        cwd=CASE_DIR,
        max_rounds=4,
        convergence_check=convergence_check,
        parallel_groups={2: ['JavaDeveloper', 'PythonDeveloper']},
    )

    print(f'\n{"=" * 60}')
    print('执行完成')
    print(f'  总轮次: {result.rounds}')
    print('  Agent 执行记录:')
    for ar in result.agents_run:
        print(
            f'    Round {ar["round"]} {ar["agent"]}: '
            f'{ar["turns"]} turns, {ar["tool_calls"]} tools, '
            f'{ar["tokens"]:,} tokens, cwd={ar.get("cwd", "-")}'
        )
    print(f'  总 Token: {result.total_tokens:,}')
    print(f'  最终状态: {result.final_status}')
    print(f'\n运行验证: python cases/multiagent_enterprise/verify.py')
    return result


if __name__ == '__main__':
    main()
