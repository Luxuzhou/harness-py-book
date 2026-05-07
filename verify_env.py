"""验证 .env 配置：从仓库根 .env 读取并掩码打印 API_KEY / BASE_URL / MODEL。"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
env_file = ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(ROOT))
from harness_py.config import ModelConfig

m = ModelConfig.from_env()
print(f"API_KEY:  {m.api_key[:8]}...{m.api_key[-4:] if len(m.api_key) > 12 else ''}")
print(f"BASE_URL: {m.base_url}")
print(f"MODEL:    {m.model}")
