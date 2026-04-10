"""
Case 1: 遗留系统重构 — 一键运行脚本
====================================
用法: python cases/refactor/run.py
需要: .env中的OPENAI_API_KEY（或HARNESS_API_KEY）
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

# 读取任务描述
task_file = Path(__file__).parent / 'TASK.md'
task = task_file.read_text(encoding='utf-8')

# 配置：工作目录指向target_project
case_dir = Path(__file__).parent
target_dir = case_dir / 'target_project'

# 设置临时数据库路径（避免使用硬编码的C:/inventory/路径）
import tempfile
tmp = tempfile.mkdtemp()
os.environ['INVENTORY_DB'] = os.path.join(tmp, 'inventory.db')

result = run(
    task,
    model_config=ModelConfig.from_env(),
    agent_config=AgentConfig(
        cwd=target_dir,
        max_iterations=40,
        planning_turns=3,  # 前3轮只读，理解代码后再改
        allow_write=True,
        allow_shell=True,
    ),
)

print(f'\n{"="*50}')
print(f'Case 1 完成')
print(f'  轮次: {result.turns}')
print(f'  工具调用: {result.tool_calls}')
print(f'  Token: {result.total_tokens:,}')
print(f'  停止原因: {result.stop_reason}')
print(f'\n运行验证: python cases/refactor/verify.py')
