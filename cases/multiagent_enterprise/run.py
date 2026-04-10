"""
Ch10 案例: 多Agent企业级跨Java+Python系统集成
==============================================
用法: python cases/multiagent_enterprise/run.py
需要: .env 中的 OPENAI_API_KEY

演示四Agent角色隔离编排:
  Round 1: Architect 分析需求 → 输出 implementation_plan.md
  Round 2: Java Dev + Python Dev 并行开发
  Round 3: QA Engineer 写测试 + 跑测试
  Round 4: 修复失败的测试（条件触发）
"""

import os
import re
import sys
from pathlib import Path

# 加载 .env
project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(project_root))

from harness_py_pro import ModelConfig
from harness_py_pro.swarm import orchestrate, AgentRole

case_dir = Path(__file__).parent

# ── 读取角色定义 ──────────────────────────────────

architect_prompt = (case_dir / 'roles' / 'architect.md').read_text(encoding='utf-8')
java_dev_prompt = (case_dir / 'roles' / 'java_developer.md').read_text(encoding='utf-8')
python_dev_prompt = (case_dir / 'roles' / 'python_developer.md').read_text(encoding='utf-8')
qa_prompt = (case_dir / 'roles' / 'qa_engineer.md').read_text(encoding='utf-8')

# 读取任务定义和上下文
task = (case_dir / 'TASK.md').read_text(encoding='utf-8')
requirement = (case_dir / 'spec' / 'requirement.md').read_text(encoding='utf-8')
architecture = (case_dir / 'spec' / 'architecture.md').read_text(encoding='utf-8')
api_contract = (case_dir / 'spec' / 'api_contract.yaml').read_text(encoding='utf-8')

# 将需求文档作为上下文注入到各角色
context_block = f"""
---
以下是项目的核心文档，请在执行任务时参考：

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

# ── 定义四个角色 ──────────────────────────────────

roles = [
    # Round 1: Architect — 只读分析，输出 plan
    AgentRole(
        name='Architect',
        role_prompt=architect_prompt + context_block,
        tool_filter=['read_file', 'grep_search', 'glob_search', 'write_file'],
        max_iterations=12,
        planning_turns=1,
        allow_shell=False,
    ),
    # Round 2a: Java Developer — 编写 Java 端代码
    AgentRole(
        name='JavaDeveloper',
        role_prompt=java_dev_prompt + context_block,
        tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search'],
        max_iterations=20,
        planning_turns=2,
        cwd=str(case_dir / 'java_module'),
    ),
    # Round 2b: Python Developer — 编写 Python 端代码
    AgentRole(
        name='PythonDeveloper',
        role_prompt=python_dev_prompt + context_block,
        tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search'],
        max_iterations=20,
        planning_turns=2,
        cwd=str(case_dir / 'python_module'),
    ),
    # Round 3: QA Engineer — 写测试并执行
    AgentRole(
        name='QAEngineer',
        role_prompt=qa_prompt + context_block,
        tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search', 'glob_search'],
        max_iterations=15,
        planning_turns=1,
        allow_write=True,
    ),
]


def convergence_check(round_num, work_dir):
    """检查是否收敛 — 所有测试通过且测试报告标记为 PASS。"""
    report_file = work_dir / 'test_report.md'
    if not report_file.exists():
        return False, 'test_report.md 尚未生成'

    content = report_file.read_text(encoding='utf-8')

    # 检查是否有失败的测试
    fail_match = re.search(r'失败[：:]\s*(\d+)', content)
    if fail_match:
        fail_count = int(fail_match.group(1))
        if fail_count == 0:
            return True, '所有测试通过，无失败项'
        return False, f'仍有 {fail_count} 个测试失败'

    # 备选：检查 PASS 标记
    if 'ALL PASS' in content.upper() or '全部通过' in content:
        return True, '测试报告标记为全部通过'

    return False, '无法判断测试状态'


# ── 执行四轮编排 ──────────────────────────────────

print('=' * 60)
print('Ch10: 多Agent企业级案例 — 跨Java+Python系统集成')
print('=' * 60)
print(f'工作目录: {case_dir}')
print(f'角色数量: {len(roles)}')
print()

result = orchestrate(
    task,
    roles,
    model_config=ModelConfig.from_env(),
    cwd=case_dir,
    max_rounds=4,
    convergence_check=convergence_check,
    # Round 2 的 JavaDeveloper 和 PythonDeveloper 并行执行
    parallel_groups={2: ['JavaDeveloper', 'PythonDeveloper']},
)

# ── 输出执行摘要 ──────────────────────────────────

print(f'\n{"=" * 60}')
print('执行完成')
print(f'  总轮次: {result.rounds}')
print(f'  Agent 执行记录:')
for ar in result.agents_run:
    print(
        f'    Round {ar["round"]} {ar["agent"]}: '
        f'{ar["turns"]} turns, {ar["tool_calls"]} tools, '
        f'{ar["tokens"]:,} tokens'
    )
print(f'  总 Token: {result.total_tokens:,}')
print(f'  最终状态: {result.final_status}')
print(f'\n运行验证: python cases/multiagent_enterprise/verify.py')
