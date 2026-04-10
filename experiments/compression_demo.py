"""
压缩实验：用DeepSeek验证四级压缩
用法: python experiments/compression_demo.py
需要: .env中的OPENAI_API_KEY
"""
import os, sys
from pathlib import Path

for line in (Path(__file__).parent.parent / '.env').read_text().splitlines():
    if line.strip() and not line.startswith('#') and '=' in line:
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(Path(__file__).parent.parent))
from harness_py.agent import run
from harness_py.config import ModelConfig, AgentConfig

result = run(
    '请逐个读取当前目录下的.py文件，对每个文件用3句话总结功能。',
    model_config=ModelConfig.from_env(),
    agent_config=AgentConfig(
        cwd=Path(__file__).parent.parent,
        max_iterations=15,
        allow_write=False,
        allow_shell=False,
        compress_threshold_pct=0.05,  # 极低阈值，确保触发压缩
    ),
)
print(f'\n结果: turns={result.turns} tools={result.tool_calls} stop={result.stop_reason}')
