"""
Ch11 案例：跨 Java / Python 真实业务代码的多 Agent 编排。

本案例**不自建业务代码**。它直接把：
- Java 后端：`cases/refactor_enterprise/target_project/`（第9章的 Spring Boot 项目）
- Python 后端：`cases/data_compliance/target_service/`（第10章的 FastAPI 合规服务）

作为两个 Developer 角色的真实工作目录，由 Harness 的 orchestrate() 协调：
- Architect 统筹读取两边 spec 并输出 implementation_plan.md
- JavaDeveloper   在第9章 target_project 里工作（cwd 指向 Java 项目根）
- PythonDeveloper 在第10章 target_service 里工作（cwd 指向 Python 项目根）
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


def _load_anchor_projects() -> tuple[Path, Path]:
    """定位第9章 Java 项目与第10章 Python 服务的根目录。"""
    java_root = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
    python_root = REPO_ROOT / 'cases' / 'data_compliance' / 'target_service'
    if not java_root.exists():
        raise FileNotFoundError(
            f'第9章 Java 项目目录不存在: {java_root}. '
            f'请先确认 cases/refactor_enterprise 已就位。')
    if not python_root.exists():
        raise FileNotFoundError(
            f'第10章 Python 服务目录不存在: {python_root}. '
            f'请先确认 cases/data_compliance 已就位。')
    return java_root, python_root


def _build_context_block(java_root: Path, python_root: Path) -> str:
    """把需求、契约、架构、第9/10章目标项目的定位拼成共享上下文。"""
    requirement = (CASE_DIR / 'spec' / 'requirement.md').read_text(encoding='utf-8')
    architecture = (CASE_DIR / 'spec' / 'architecture.md').read_text(encoding='utf-8')
    api_contract = (CASE_DIR / 'spec' / 'api_contract.yaml').read_text(encoding='utf-8')

    context = f"""
---
## 目标系统定位

本任务在两个真实业务代码库上同时进行：
- **Java 端**（第9章案例）：`{java_root}`
  完整的临床路径管理 Spring Boot 项目，92 个生产源文件 / 约 10,127 行生产代码。
- **Python 端**（第10章案例）：`{python_root}`
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

## 本实验硬性交付边界

本章验证的是跨项目多 Agent 编排，不是重做两端已有 anomaly 基础模块。当前基线中 Java/Python 两端可能已经存在部分
Controller、Service、DTO、Analyzer 或测试代码；Agent 必须先识别已有实现，再只补齐跨端集成缺口。

必须完成的 P0 交付物：
1. Java 端必须在 `src/main/java/com/example/cp/client/` 下新增或补全调用 Python 分析服务的 HTTP 客户端，例如
   `PythonAnalysisClient.java`。该客户端至少要覆盖实时分析和历史分析调用，并设置 `X-Service-Token` 与 `X-Trace-Id`。
2. Python 端必须保证 `app/clients/java_api_client.py` 可以按契约调用 Java 端规则查询与异常事件上报。
3. QA 只有在 Java 主代码客户端、Python 客户端、契约测试和两端相关测试均存在且通过时，才可以写 `FINAL_STATUS: PASS`。

如果 `src/main/java/com/example/cp/client/*.java` 不存在，本实验不得收敛。
---
"""
    return context


def _build_roles(java_root: Path, python_root: Path):
    from harness_py_pro.swarm import AgentRole

    architect_prompt = (CASE_DIR / 'roles' / 'architect.md').read_text(encoding='utf-8')
    java_dev_prompt = (CASE_DIR / 'roles' / 'java_developer.md').read_text(encoding='utf-8')
    python_dev_prompt = (CASE_DIR / 'roles' / 'python_developer.md').read_text(encoding='utf-8')
    qa_prompt = (CASE_DIR / 'roles' / 'qa_engineer.md').read_text(encoding='utf-8')

    context_block = _build_context_block(java_root, python_root)

    PLAN_TOOLS = [
        'update_plan', 'checklist_write', 'checklist_update', 'checklist_list',
        'task_create', 'task_list', 'task_update', 'task_cancel',
    ]
    SHARED_ROOT = '../../multiagent_enterprise'

    return [
        # Round 1：Architect 统揽第9章 Java 与第10章 Python，产出 implementation_plan.md
        AgentRole(
            name='Architect',
            role_prompt=architect_prompt + context_block,
            tool_filter=['read_file', 'grep_search', 'glob_search', 'write_file'] + PLAN_TOOLS,
            max_iterations=24,
            planning_turns=0,
            allow_shell=False,
            cwd=CASE_DIR,  # 只能改编排目录下的 implementation_plan.md
            sandbox_mode='bypass',
            network_isolated=True,
            allowed_paths=['.', '../refactor_enterprise/target_project', '../data_compliance/target_service'],
            read_only_paths=['../refactor_enterprise/target_project', '../data_compliance/target_service'],
            filesystem_roots=['..', '../..'],
        ),
        # Round 2a：JavaDeveloper 在第9章 Java 项目里工作
        AgentRole(
            name='JavaDeveloper',
            role_prompt=java_dev_prompt + context_block,
            tool_filter=['read_file', 'write_file', 'edit_file', 'batch_edit_file',
                         'bash', 'grep_search', 'glob_search', 'acceptance_check'] + PLAN_TOOLS,
            max_iterations=36,
            planning_turns=0,
            acceptance_commands=[
                'python -B -c "from pathlib import Path; p=Path(\'src/main/java/com/example/cp/client\'); files=list(p.glob(\'*.java\')); assert files, \'missing Java client source under src/main/java/com/example/cp/client\'"',
                'mvn -DskipTests compile',
            ],
            acceptance_timeout=300,
            cwd=java_root,
            sandbox_mode='bypass',
            network_isolated=True,
            allowed_paths=['.', SHARED_ROOT],
            read_only_paths=[f'{SHARED_ROOT}/spec'],
            filesystem_roots=[SHARED_ROOT],
        ),
        # Round 2b：PythonDeveloper 在第10章 Python 服务里工作（与 Java 并行）
        AgentRole(
            name='PythonDeveloper',
            role_prompt=python_dev_prompt + context_block,
            tool_filter=['read_file', 'write_file', 'edit_file', 'batch_edit_file',
                         'bash', 'grep_search', 'glob_search', 'acceptance_check'] + PLAN_TOOLS,
            max_iterations=36,
            planning_turns=0,
            acceptance_commands=[
                'python -B -m pytest tests/test_anomaly_analyzer.py tests/test_anomaly_rule_engine.py tests/test_contract_consistency.py tests/test_java_api_client.py -q -p no:cacheprovider',
            ],
            acceptance_timeout=300,
            cwd=python_root,
            sandbox_mode='bypass',
            network_isolated=True,
            allowed_paths=['.', SHARED_ROOT],
            read_only_paths=[f'{SHARED_ROOT}/spec'],
            filesystem_roots=[SHARED_ROOT],
        ),
        # Round 3：QAEngineer 回到编排目录做跨项目契约校验
        AgentRole(
            name='QAEngineer',
            role_prompt=qa_prompt + context_block,
            tool_filter=['read_file', 'write_file', 'edit_file', 'batch_edit_file',
                         'bash', 'grep_search', 'glob_search', 'acceptance_check'] + PLAN_TOOLS,
            max_iterations=44,
            planning_turns=0,
            acceptance_commands=[
                'cd ../data_compliance/target_service && python -B -m pytest tests/test_anomaly_analyzer.py tests/test_anomaly_rule_engine.py tests/test_contract_consistency.py tests/test_java_api_client.py -q -p no:cacheprovider',
                'cd ../refactor_enterprise/target_project && mvn "-Dtest=PythonServiceClientTest,AnomalyControllerTest,AnomalyServiceTest" test',
                'python -B verify.py',
            ],
            acceptance_timeout=300,
            allow_write=True,
            cwd=CASE_DIR,
            sandbox_mode='bypass',
            network_isolated=True,
            allowed_paths=['.', '../refactor_enterprise/target_project', '../data_compliance/target_service'],
            read_only_paths=[
                '../refactor_enterprise/target_project/src/main',
                '../data_compliance/target_service/app',
            ],
            filesystem_roots=['..', '../..'],
        ),
    ]


def _missing_required_artifacts() -> list[str]:
    java_root = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
    py_root = REPO_ROOT / 'cases' / 'data_compliance' / 'target_service'

    missing: list[str] = []
    if not (py_root / 'tests' / 'test_java_api_client.py').exists():
        missing.append('cases/data_compliance/target_service/tests/test_java_api_client.py')

    java_test_candidates = [
        java_root / 'src' / 'test' / 'java' / 'com' / 'example' / 'cp' / 'client' / 'PythonServiceClientTest.java',
        java_root / 'src' / 'test' / 'java' / 'com' / 'example' / 'cp' / 'client' / 'PythonAnalysisClientTest.java',
    ]
    if not any(path.exists() for path in java_test_candidates):
        missing.append('cases/refactor_enterprise/target_project/src/test/java/com/example/cp/client/PythonServiceClientTest.java')

    java_client_dir = java_root / 'src' / 'main' / 'java' / 'com' / 'example' / 'cp' / 'client'
    if not java_client_dir.exists() or not any(java_client_dir.glob('*.java')):
        missing.append('cases/refactor_enterprise/target_project/src/main/java/com/example/cp/client/*.java')
    return missing


def convergence_check(round_num, work_dir):
    """收敛条件：test_report.md 存在且没有失败项。"""
    if round_num < 3:
        return False, 'QA 尚未执行，不能根据旧 test_report.md 收敛'
    report_file = work_dir / 'test_report.md'
    if not report_file.exists():
        return False, 'test_report.md 尚未生成'
    content = report_file.read_text(encoding='utf-8')
    bad_patterns = [
        r'(?:失败|Failed)[：:]\s*[1-9]\d*',
        r'(?:已知代码缺陷|Known defects)[：:：]?\s*\**[1-9]\d*',
        r'(?:缺陷|Defects)[：:]\s*[1-9]\d*',
    ]
    for pattern in bad_patterns:
        if re.search(pattern, content, flags=re.IGNORECASE):
            return False, '测试报告仍记录失败或代码缺陷'
    contradiction_patterns = [
        r'##\s*已知问题(?!\s*[:：]?\s*(无|None|0))',
        r'(?:建议修复|需由.*补充|优先级\s*[:：]\s*P[0-9])',
        r'(?:known issues?|recommended fix|priority\s*[:：]\s*P[0-9])',
    ]
    for pattern in contradiction_patterns:
        if re.search(pattern, content, flags=re.IGNORECASE):
            return False, '测试报告声称 PASS 但仍包含未解决问题'
    missing_artifacts = _missing_required_artifacts()
    if missing_artifacts:
        return False, '测试报告 PASS 前仍缺少交付物: ' + ', '.join(missing_artifacts)

    pass_markers = [
        'FINAL_STATUS: PASS',
        '最终状态: PASS',
        '最终结论: PASS',
    ]
    if any(marker in content for marker in pass_markers):
        return True, '测试报告给出明确 PASS 标记，且未记录失败/缺陷'

    zero_fail = re.search(r'(?:失败|Failed)[：:]\s*0', content, flags=re.IGNORECASE)
    if zero_fail and ('ALL PASS' in content.upper() or '全部通过' in content):
        return True, '所有测试通过，无失败项'

    return False, '缺少明确 FINAL_STATUS: PASS 标记'


def _reset_run_artifacts(java_root: Path, python_root: Path) -> None:
    """Remove stale generated state so convergence cannot use old artifacts."""
    for path in [
        CASE_DIR / 'implementation_plan.md',
        CASE_DIR / 'test_report.md',
        CASE_DIR / 'nul',
    ]:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    for root in [CASE_DIR, java_root, python_root]:
        session_dir = root / '.harness_sessions'
        for state_name in ['plan_state.json', 'checklist_state.json', 'tasks.json']:
            try:
                (session_dir / state_name).unlink(missing_ok=True)
            except OSError:
                pass


def main():
    from harness_py_pro import ModelConfig
    from harness_py_pro.swarm import orchestrate

    java_root, python_root = _load_anchor_projects()
    _reset_run_artifacts(java_root, python_root)

    print('=' * 60)
    print('Ch11: 跨 Java + Python 真实业务代码的多 Agent 编排')
    print('=' * 60)
    print(f'编排目录:  {CASE_DIR}')
    print(f'Java 端 cwd (第9章): {java_root}')
    print(f'Python 端 cwd (第10章): {python_root}')
    print()

    task = (CASE_DIR / 'TASK.md').read_text(encoding='utf-8')
    roles = _build_roles(java_root, python_root)

    result = orchestrate(
        task,
        roles,
        model_config=ModelConfig.from_env(),
        cwd=CASE_DIR,
        max_rounds=5,
        convergence_check=convergence_check,
        parallel_groups={
            2: ['JavaDeveloper', 'PythonDeveloper'],
            4: ['JavaDeveloper', 'PythonDeveloper'],
        },
        round_plan={
            1: ['Architect'],
            2: ['JavaDeveloper', 'PythonDeveloper'],
            3: ['QAEngineer'],
            4: ['JavaDeveloper', 'PythonDeveloper'],
            5: ['QAEngineer'],
        },
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
