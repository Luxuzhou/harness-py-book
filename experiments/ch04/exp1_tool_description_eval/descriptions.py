"""
descriptions.py
================
两套工具描述：
- V1：harness_py_pro/tools.py 当前版本（最小化描述）
- V2：遵循 Claude Code + MCP 社区最佳实践的优化版
      - 明确"DO NOT"负向约束
      - 指向正确的替代工具
      - 补全参数语义（如 offset 是0-based）

eval_runner.py 会在创建 Registry 后根据 --version 参数
用这里的描述覆盖 BaseTool.get_schema()['description']。
"""

from __future__ import annotations


V1_DESCRIPTIONS: dict[str, str] = {
    'read_file': '读取文件内容。支持行号范围。',
    'write_file': '写入文件（创建或覆盖）。自动创建父目录。',
    'edit_file': '精确替换文件中的字符串。old_string必须在文件中唯一匹配。',
    'grep_search': '正则搜索文件内容。',
    'glob_search': '按glob模式搜索文件。',
    'bash': '执行shell命令。用于运行测试、脚本等。',
}


V2_DESCRIPTIONS: dict[str, str] = {
    'read_file': (
        'Read ONE file\'s full contents. Returns text with line numbers.\n'
        'USE WHEN: user wants to see the content of a specific file path.\n'
        'DO NOT USE FOR:\n'
        '  - finding files by name pattern → use glob_search\n'
        '  - searching content across files → use grep_search\n'
        '  - binary files, directories, URLs\n'
        'If user says "cat/head/tail/less/more <file>" translate it to THIS tool, '
        'not bash. "head -20 X" maps to read_file(path=X, offset=0, limit=20). '
        '"tail X" maps to read_file(path=X, offset=<near_end>).\n'
        'Args: path (required), offset (0-based line, default 0), limit (default 2000).'
    ),
    'write_file': (
        'Create a NEW file OR completely overwrite an existing file.\n'
        'USE WHEN: creating a brand-new file, OR replacing >80% of a file\'s content.\n'
        'DO NOT USE FOR:\n'
        '  - changing a few lines, a function name, a version number → use edit_file\n'
        '  - modifying existing files where most content stays → use edit_file\n'
        'Parent directories are auto-created.\n'
        'Args: path, content.'
    ),
    'edit_file': (
        'Replace ONE exact string in an existing file with a new string.\n'
        'USE WHEN: changing part of a file — a function name, a value, one line, one block.\n'
        'TYPICAL WORKFLOW: first call read_file to see current content, then call edit_file '
        'with a unique old_string (include enough surrounding context to make it unique).\n'
        'ERRORS: old_string must match EXACTLY (whitespace matters). '
        'Zero matches = file unchanged (expand context). '
        'Multiple matches = error (expand context until unique).\n'
        'DO NOT USE FOR: creating new files, rewriting whole files → use write_file.\n'
        'Args: path, old_string, new_string.'
    ),
    'grep_search': (
        'Search file CONTENTS by regex. Returns "path:line_number:matching_line".\n'
        'USE WHEN: finding where a function/variable/string appears in code, '
        'locating TODO markers, finding import statements.\n'
        'NEVER use bash grep/rg/ack/ag — ALWAYS use this tool for content search. '
        'This tool already handles encoding and excludes binary files.\n'
        'DO NOT USE FOR: listing files by name pattern → use glob_search (this returns '
        'content matches, not filenames).\n'
        'Args: pattern (regex, required), path (default "."), include (glob filter e.g. "*.py").'
    ),
    'glob_search': (
        'List file PATHS matching a glob pattern (e.g. "**/*.py", "src/**/*.ts").\n'
        'USE WHEN: finding files by name or extension — "all python files", '
        '"all tests", "markdown docs".\n'
        'NEVER use bash ls/find/dir/tree — ALWAYS use this tool to list files. '
        'If user says "ls *.py" or "find . -name X.md", translate it to THIS tool\'s '
        'pattern, not bash.\n'
        'Returns PATHS only (no file content) — follow up with read_file if needed.\n'
        'DO NOT USE FOR: searching inside files → use grep_search.\n'
        'Args: pattern (required, relative path only), path (default ".").'
    ),
    'bash': (
        'Execute a shell command. Use ONLY for tasks that have NO dedicated tool.\n'
        'VALID USE CASES:\n'
        '  - Running tests: pytest, jest, go test\n'
        '  - Git operations: git status, git log, git diff\n'
        '  - Package management: pip install, npm install, cargo build\n'
        '  - Starting services: python main.py, npm run dev, docker up\n'
        '  - Custom scripts that do NOT map to file/search operations\n'
        'NEVER use bash for these — use the dedicated tool instead:\n'
        '  - cat / head / tail / less / more           → read_file\n'
        '  - ls / find / dir / tree                    → glob_search\n'
        '  - grep / rg / ack / ag                      → grep_search\n'
        '  - sed / awk / echo > file / printf > file   → edit_file or write_file\n'
        'When user literally types "cat X" or "ls *.py", TRANSLATE to the dedicated '
        'tool — do not execute it as bash.\n'
        'Args: command (required), timeout (seconds, default 120).'
    ),
}


def apply_descriptions(registry, version: str) -> None:
    """将指定版本的描述应用到 registry 的工具上。"""
    if version == 'v1':
        descs = V1_DESCRIPTIONS
    elif version == 'v2':
        descs = V2_DESCRIPTIONS
    else:
        raise ValueError(f'未知版本: {version}，只支持 v1/v2')

    for name, new_desc in descs.items():
        tool = registry.get(name)
        if tool is None:
            continue
        original_get_schema = tool.get_schema

        def make_patched(orig, desc):
            def patched():
                schema = orig()
                schema['description'] = desc
                return schema
            return patched

        tool.get_schema = make_patched(original_get_schema, new_desc)
