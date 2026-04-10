"""
Case 2: 医疗数据分析 — 一键运行脚本
=====================================
用法: python cases/medical/run.py
需要: .env中的OPENAI_API_KEY
"""

import os
import sys
from pathlib import Path

# 加载.env
project_root = Path(__file__).parent.parent.parent
env_file = project_root / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(project_root))

from harness_py_pro import run, ModelConfig, AgentConfig
from harness_py_pro.config import HookConfig

# 导入合规hooks
sys.path.insert(0, str(Path(__file__).parent))
from compliance_hooks import pre_tool_hook, post_tool_hook

# 读取任务
task = (Path(__file__).parent / 'TASK.md').read_text(encoding='utf-8')

case_dir = Path(__file__).parent

result = run(
    task,
    model_config=ModelConfig.from_env(),
    agent_config=AgentConfig(
        cwd=case_dir,
        max_iterations=30,
        planning_turns=2,
        allow_write=True,
        allow_shell=True,
        # 路径限制
        allowed_paths=['sample_data', '.'],
        denied_paths=[],
        # 合规hooks
        hooks=HookConfig(
            pre_tool=pre_tool_hook,
            post_tool=post_tool_hook,
        ),
    ),
)

print(f'\n{"="*50}')
print(f'Case 2 完成')
print(f'  轮次: {result.turns}')
print(f'  工具调用: {result.tool_calls}')
print(f'  Token: {result.total_tokens:,}')
print(f'  合规警告: {len(result.hook_warnings)} 条')
print(f'  停止原因: {result.stop_reason}')
print(f'\n运行验证: python cases/medical/verify.py')
