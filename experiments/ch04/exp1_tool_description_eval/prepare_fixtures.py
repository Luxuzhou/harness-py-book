"""
prepare_fixtures.py
====================
为工具描述eval生成固定的测试沙箱。

运行后在 ./eval_sandbox/ 目录生成一批"假项目文件"，
golden_set.jsonl 里的任务都基于这些文件提问。

用法:
    cd experiments/ch04/exp1_tool_description_eval/
    python prepare_fixtures.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

SANDBOX = Path(__file__).parent / 'eval_sandbox'


def _write(rel_path: str, content: str) -> None:
    full = SANDBOX / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding='utf-8')


def prepare() -> None:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True)

    # 根级文档
    _write('README.md', (
        '# Demo Project\n\n'
        '这是一个用于工具描述eval的示例项目。\n\n'
        '## 功能\n\n'
        '- 配置管理\n'
        '- 工具函数\n'
        '- 单元测试\n\n'
        '详见 docs/guide.md。\n'
    ))

    _write('requirements.txt', (
        'flask==2.0.0\n'
        'requests==2.28.0\n'
        'pytest==7.1.0\n'
        'pyyaml==6.0\n'
    ))

    _write('.gitignore', '*.pyc\n__pycache__/\n.venv/\n')

    # 根级 Python 源码
    _write('config.py', (
        '"""项目配置。"""\n\n'
        'VERSION = "1.0.0"\n'
        'DEBUG = False\n\n'
        '# TODO: 支持从环境变量加载\n'
        'def old_name():\n'
        '    """旧版入口函数。"""\n'
        '    return VERSION\n\n'
        '\n'
        'def get_config():\n'
        '    return {"version": VERSION, "debug": DEBUG}\n'
    ))

    _write('utils.py', (
        '"""工具函数。"""\n\n'
        'import os\n'
        'import re\n\n'
        '# FIXME: 处理空字符串\n'
        'def helper_foo(text: str) -> str:\n'
        '    return text.strip()\n\n'
        '\n'
        'def parse_number(s: str) -> int:\n'
        '    return int(s)\n'
    ))

    _write('main.py', (
        '"""应用入口。"""\n\n'
        'import requests\n'
        'from config import VERSION\n'
        'from utils import helper_foo\n\n'
        'print("debug")  # 调试用\n\n'
        '\n'
        'def main():\n'
        '    print(f"App v{VERSION}")\n'
        '    helper_foo("hello")\n\n'
        '\n'
        'if __name__ == "__main__":\n'
        '    main()\n'
    ))

    # tests/
    _write('tests/__init__.py', '')

    _write('tests/test_config.py', (
        '"""配置测试。"""\n\n'
        'from config import VERSION, get_config\n\n'
        '# TODO: 增加环境变量测试\n'
        'def test_version():\n'
        '    assert VERSION == "1.0.0"\n\n'
        '\n'
        'def test_get_config():\n'
        '    cfg = get_config()\n'
        '    assert cfg["version"] == "1.0.0"\n'
    ))

    _write('tests/test_utils.py', (
        '"""工具函数测试。"""\n\n'
        'from utils import helper_foo, parse_number\n\n'
        'def test_helper_foo():\n'
        '    assert helper_foo("  hi  ") == "hi"\n\n'
        '\n'
        'def test_parse_number():\n'
        '    assert parse_number("42") == 42\n'
    ))

    # src/
    _write('src/__init__.py', '')

    _write('src/parser.py', (
        '"""解析模块。"""\n\n'
        'import re\n\n'
        '\n'
        'def parse_line(line: str) -> dict:\n'
        '    return {"raw": line}\n'
    ))

    _write('src/writer.py', (
        '"""写入模块。"""\n\n'
        'import json\n\n'
        '\n'
        'class Writer:\n'
        '    def __init__(self, path: str):\n'
        '        self.path = path\n\n'
        '    def write(self, data):\n'
        '        with open(self.path, "w") as f:\n'
        '            json.dump(data, f)\n'
    ))

    # docs/
    _write('docs/guide.md', (
        '# 使用指南\n\n'
        '## 旧版说明\n\n'
        '这是旧版的使用说明。Harness Engineering相关内容见别处。\n\n'
        '## 安装\n\n'
        '```bash\n'
        'pip install -r requirements.txt\n'
        '```\n'
    ))

    # data/
    _write('data/sample.txt', (
        'apple\n'
        'banana\n'
        'cherry\n'
    ))

    files = sorted(str(p.relative_to(SANDBOX)) for p in SANDBOX.rglob('*') if p.is_file())
    print(f'[prepare_fixtures] 已生成 {len(files)} 个fixture文件 → {SANDBOX}')
    for f in files:
        print(f'  - {f}')


if __name__ == '__main__':
    prepare()
