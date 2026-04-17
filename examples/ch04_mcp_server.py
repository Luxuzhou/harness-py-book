"""
第4章 MCP Server 最小示例
==========================
独立的MCP协议演示，不依赖harness_py（因为MCP是外部协议）。
MCP Server本质上是独立进程，通过stdio与Agent通信。

用法:
  测试模式: python examples/ch04_mcp_server.py --test
  Server模式: python examples/ch04_mcp_server.py
"""

# MCP Server的完整实现在standalone/目录（因其作为独立进程运行）
import sys
from pathlib import Path

_impl = Path(__file__).parent.parent / 'standalone' / 'ch04_mcp_server.py'
if _impl.exists():
    exec(compile(_impl.read_text(encoding='utf-8'), str(_impl), 'exec'))
else:
    print(f'Error: MCP Server implementation not found at {_impl}')
    sys.exit(1)
