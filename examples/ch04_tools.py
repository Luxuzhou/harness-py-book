"""
第4章 工具系统演示
==================
直接调用harness_py框架的6个工具，逐个验证。

用法: python examples/ch04_tools.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from harness_py.config import AgentConfig
from harness_py.tools import (
    tool_read_file, tool_write_file, tool_edit_file,
    tool_grep_search, tool_glob_search, tool_bash,
    find_best_bash, smart_decode, TOOL_SCHEMAS,
)


def main():
    with tempfile.TemporaryDirectory() as d:
        cfg = AgentConfig(cwd=Path(d))

        # 准备测试文件
        (Path(d) / 'src').mkdir()
        (Path(d) / 'src' / 'main.py').write_text(
            'def hello():\n    return "world"\n\ndef add(a, b):\n    return a + b\n',
            encoding='utf-8',
        )
        (Path(d) / 'src' / 'utils.py').write_text('import os\n', encoding='utf-8')

        tests = [
            ('read_file', lambda: tool_read_file({'path': 'src/main.py'}, cfg)),
            ('write_file', lambda: tool_write_file({'path': 'output/report.md', 'content': '# Report\nDone.'}, cfg)),
            ('edit_file', lambda: tool_edit_file({
                'path': 'src/main.py', 'old_string': 'return "world"', 'new_string': 'return "hello world"'
            }, cfg)),
            ('grep_search', lambda: tool_grep_search({'pattern': r'def \w+', 'path': 'src'}, cfg)),
            ('glob_search', lambda: tool_glob_search({'pattern': '**/*.py'}, cfg)),
        ]

        print('=== 第4章 工具系统验证 ===\n')
        print(f'工具Schema数: {len(TOOL_SCHEMAS)}')
        for s in TOOL_SCHEMAS:
            print(f"  {s['function']['name']}: {s['function']['description'][:50]}")

        print(f'\nBash路径: {find_best_bash() or "未找到"}')
        print(f'smart_decode测试: {smart_decode(b"hello")} | {smart_decode(b"")} | BOM: {smart_decode(b"\\xff\\xfeh\\x00i\\x00")}')

        print()
        passed = 0
        for name, fn in tests:
            ok, result = fn()
            status = 'PASS' if ok else 'FAIL'
            print(f'  {status} {name}: {result[:80]}')
            if ok:
                passed += 1

        # bash（如果有bash路径）
        bash_path = find_best_bash()
        if bash_path:
            ok, result = tool_bash({'command': 'echo "hello from bash"'}, cfg)
            print(f'  {"PASS" if ok else "FAIL"} bash: {result.strip()[:80]}')
            if ok:
                passed += 1
        else:
            print(f'  SKIP bash: 未找到Git Bash')

        # 安全测试：路径遍历
        print('\n--- 安全测试 ---')
        ok, result = tool_read_file({'path': '../../etc/passwd'}, cfg)
        print(f'  {"BLOCK" if not ok else "LEAK!"} 路径遍历: {result[:60]}')

        ok, result = tool_write_file({'path': '../../evil.txt', 'content': 'pwned'}, cfg)
        print(f'  {"BLOCK" if not ok else "LEAK!"} 写出cwd: {result[:60]}')

        total = 5 + (1 if bash_path else 0)
        print(f'\n结果: {passed}/{total} 工具测试通过')


if __name__ == '__main__':
    main()
