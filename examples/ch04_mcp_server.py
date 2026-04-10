"""
第4章 MCP Server 最小示例
==========================
独立的MCP协议演示，不依赖harness_py（因为MCP是外部协议）。
从 standalone/ch04_mcp_server.py 保留，因为MCP Server本质上是独立进程。

用法:
  测试模式: python examples/ch04_mcp_server.py --test
  Server模式: python examples/ch04_mcp_server.py
"""

# 直接引用原standalone版本（MCP Server是独立进程，不适合做薄包装）
import sys
from pathlib import Path

# 复用standalone版本
standalone = Path(__file__).parent.parent / 'standalone' / 'ch04_mcp_server.py'
if standalone.exists():
    exec(compile(standalone.read_text(encoding='utf-8'), str(standalone), 'exec'))
else:
    print(f'Error: {standalone} not found')
    print('MCP Server demo requires standalone/ch04_mcp_server.py')
    sys.exit(1)
