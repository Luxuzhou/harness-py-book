"""
6个核心工具 + 工具注册表
=========================
Ch4工具层。包含我们验证过的跨平台修复：
- 线程读取subprocess（替代selector）
- Git Bash优先（避开WSL）
- 编码自适应（from_utf8_lossy对齐）
"""
from __future__ import annotations

import os
import re
import sys
import shutil
import subprocess
import threading
import queue
import time
from pathlib import Path

from .config import AgentConfig


def smart_decode(raw: bytes) -> str:
    """对齐Rust的String::from_utf8_lossy。UTF-16 BOM是唯一的例外。"""
    if not raw:
        return ''
    if raw[:2] == b'\xff\xfe':
        return raw[2:].decode('utf-16-le', errors='replace')
    return raw.decode('utf-8', errors='replace')


def find_best_bash() -> str | None:
    """优先Git Bash，避开WSL bash（可能没装分发）。"""
    if sys.platform != 'win32':
        return shutil.which('bash') or '/bin/bash'
    for candidate in [
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git' / 'bin' / 'bash.exe',
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git' / 'usr' / 'bin' / 'bash.exe',
    ]:
        if candidate.exists():
            return str(candidate)
    found = shutil.which('bash')
    if found and 'WindowsApps' not in found:
        return found
    return None


# ====================
# 工具定义（JSON Schema，供LLM理解如何调用）
# ====================

TOOL_SCHEMAS = [
    {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': 'Read a file. Use offset/limit for large files.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'File path'},
                    'offset': {'type': 'integer', 'description': 'Start line (0-based)'},
                    'limit': {'type': 'integer', 'description': 'Max lines to read'},
                },
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'write_file',
            'description': 'Write content to a file. Creates parent directories if needed.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'File path'},
                    'content': {'type': 'string', 'description': 'File content'},
                },
                'required': ['path', 'content'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'edit_file',
            'description': 'Replace a string in a file. old_string must match exactly.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'File path'},
                    'old_string': {'type': 'string', 'description': 'Text to find'},
                    'new_string': {'type': 'string', 'description': 'Replacement text'},
                },
                'required': ['path', 'old_string', 'new_string'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'grep_search',
            'description': 'Search for a pattern in files. Returns matching lines with file:line format.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {'type': 'string', 'description': 'Regex pattern'},
                    'path': {'type': 'string', 'description': 'File or directory to search'},
                },
                'required': ['pattern'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'glob_search',
            'description': 'Find files matching a glob pattern.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {'type': 'string', 'description': 'Glob pattern (e.g. **/*.py)'},
                    'path': {'type': 'string', 'description': 'Root directory'},
                },
                'required': ['pattern'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'bash',
            'description': 'Execute a shell command. Use for running tests, installing packages, etc.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string', 'description': 'Shell command to execute'},
                },
                'required': ['command'],
            },
        },
    },
]


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f'{text[:half]}\n... [truncated {len(text) - limit} chars] ...\n{text[-half:]}'


# ====================
# 路径安全检查
# ====================

def _check_path_escape(config: AgentConfig, raw_path: str) -> tuple[bool, str]:
    """检查路径是否逃逸出工作目录。防止 ../../etc/passwd 等路径遍历攻击。"""
    resolved = (Path(config.cwd) / raw_path).resolve()
    cwd_resolved = Path(config.cwd).resolve()
    # 使用is_relative_to而非startswith，避免前缀碰撞（如 /project vs /project_secret）
    try:
        resolved.relative_to(cwd_resolved)
    except ValueError:
        return False, f'Path escapes working directory: {raw_path}'
    return True, ''


def _check_glob_pattern_safe(pattern: str) -> tuple[bool, str]:
    normalized = pattern.replace('\\', '/')
    if normalized.startswith('/') or re.match(r'^[A-Za-z]:/', normalized):
        return False, f'Glob pattern must be relative: {pattern}'
    parts = [part for part in normalized.split('/') if part and part != '.']
    if '..' in parts:
        return False, f'Glob pattern escapes working directory: {pattern}'
    return True, ''


# ====================
# 工具实现
# ====================

def tool_read_file(args: dict, config: AgentConfig) -> tuple[bool, str]:
    ok, reason = _check_path_escape(config, args['path'])
    if not ok:
        return False, reason
    path = Path(config.cwd) / args['path']
    if not path.is_file():
        return False, f'File not found: {args["path"]}'
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        return False, f'Cannot read: {e}'
    offset = args.get('offset', 0)
    limit = args.get('limit')
    if offset or limit:
        lines = text.splitlines(keepends=True)
        end = (offset + limit) if limit else len(lines)
        text = ''.join(lines[offset:end])
    return True, truncate(text, config.max_output_chars)


def tool_write_file(args: dict, config: AgentConfig) -> tuple[bool, str]:
    if not config.allow_write:
        return False, 'Write permission denied'
    ok, reason = _check_path_escape(config, args['path'])
    if not ok:
        return False, reason
    path = Path(config.cwd) / args['path']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args['content'], encoding='utf-8')
    return True, f'Wrote {path.name} ({len(args["content"])} chars)'


def tool_edit_file(args: dict, config: AgentConfig) -> tuple[bool, str]:
    if not config.allow_write:
        return False, 'Write permission denied'
    ok, reason = _check_path_escape(config, args['path'])
    if not ok:
        return False, reason
    path = Path(config.cwd) / args['path']
    if not path.is_file():
        return False, f'File not found: {args["path"]}'
    text = path.read_text(encoding='utf-8', errors='replace')
    old = args['old_string']
    if old not in text:
        return False, f'String not found in {args["path"]}'
    count = text.count(old)
    text = text.replace(old, args['new_string'], 1)
    path.write_text(text, encoding='utf-8')
    return True, f'Replaced 1/{count} occurrence(s) in {path.name}'


def tool_grep_search(args: dict, config: AgentConfig) -> tuple[bool, str]:
    search_path = args.get('path', '.')
    ok, reason = _check_path_escape(config, search_path)
    if not ok:
        return False, reason
    root = Path(config.cwd) / search_path
    pattern = args['pattern']
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return False, f'Invalid regex: {e}'
    hits = []
    file_iter = root.rglob('*') if root.is_dir() else [root]
    for fp in file_iter:
        if not fp.is_file() or fp.suffix in ('.pyc', '.exe', '.dll', '.so'):
            continue
        try:
            text = fp.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                rel = fp.relative_to(config.cwd) if fp.is_relative_to(config.cwd) else fp
                hits.append(f'{rel}:{i}: {line}')
                if len(hits) >= 100:
                    return True, '\n'.join(hits + ['... truncated at 100 matches'])
    return True, '\n'.join(hits) if hits else '(no matches)'


def tool_glob_search(args: dict, config: AgentConfig) -> tuple[bool, str]:
    search_path = args.get('path', '.')
    ok, reason = _check_path_escape(config, search_path)
    if not ok:
        return False, reason
    ok, reason = _check_glob_pattern_safe(args['pattern'])
    if not ok:
        return False, reason
    root = Path(config.cwd) / search_path
    matches = sorted(root.glob(args['pattern']))[:100]
    lines = [str(m.relative_to(config.cwd)) if m.is_relative_to(config.cwd) else str(m) for m in matches]
    return True, '\n'.join(lines) if lines else '(no matches)'


def tool_bash(args: dict, config: AgentConfig) -> tuple[bool, str]:
    if not config.allow_shell:
        return False, 'Shell permission denied'
    command = args['command']

    # 安全检查
    if not config.allow_destructive:
        dangerous = ['rm -rf', 'rmdir /s', 'format ', 'mkfs', 'dd if=', '> /dev/']
        for d in dangerous:
            if d in command:
                return False, f'Destructive command blocked: {d}'

    bash_path = find_best_bash()
    if bash_path:
        popen_args = [bash_path, '-c', command]
        shell = False
    elif sys.platform == 'win32':
        popen_args = command
        shell = True
    else:
        popen_args = ['/bin/bash', '-c', command]
        shell = False

    # 线程读取（替代selector，跨平台安全）
    try:
        process = subprocess.Popen(
            popen_args, shell=shell, cwd=str(config.cwd),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
        )
    except OSError as e:
        return False, f'Failed to execute: {e}'

    output_queue: queue.Queue[tuple[str, bytes] | None] = queue.Queue()

    def reader(stream, name):
        try:
            while True:
                line = stream.readline()
                if not line:
                    break
                output_queue.put((name, line))
        except (OSError, ValueError):
            pass
        finally:
            output_queue.put(None)

    threads = []
    for stream, name in [(process.stdout, 'stdout'), (process.stderr, 'stderr')]:
        if stream:
            t = threading.Thread(target=reader, args=(stream, name), daemon=True)
            t.start()
            threads.append(t)

    stdout_parts, stderr_parts = [], []
    alive = len(threads)
    deadline = time.monotonic() + config.command_timeout

    while alive > 0:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            process.kill()
            return False, f'Command timed out after {config.command_timeout}s'
        try:
            item = output_queue.get(timeout=min(remaining, 0.1))
        except queue.Empty:
            if process.poll() is not None:
                break
            continue
        if item is None:
            alive -= 1
            continue
        name, raw = item
        text = smart_decode(raw)
        (stdout_parts if name == 'stdout' else stderr_parts).append(text)

    for t in threads:
        t.join(timeout=2.0)

    exit_code = process.wait()
    stdout = ''.join(stdout_parts)
    stderr = ''.join(stderr_parts)
    output = f'exit_code={exit_code}\n[stdout]\n{stdout.rstrip()}\n[stderr]\n{stderr.rstrip()}'
    return exit_code == 0, truncate(output, config.max_output_chars)


# ====================
# 工具注册表
# ====================

TOOL_REGISTRY = {
    'read_file': tool_read_file,
    'write_file': tool_write_file,
    'edit_file': tool_edit_file,
    'grep_search': tool_grep_search,
    'glob_search': tool_glob_search,
    'bash': tool_bash,
}


def get_schemas_for_phase(turn: int, config: AgentConfig) -> list[dict]:
    """根据当前轮次返回可用工具的schema。规划阶段只暴露只读工具。"""
    if turn <= config.planning_turns:
        allowed = set(config.planning_tools)
        return [s for s in TOOL_SCHEMAS if s['function']['name'] in allowed]
    return TOOL_SCHEMAS


def execute_tool(name: str, args: dict, config: AgentConfig, *, turn: int = 999) -> tuple[bool, str]:
    """执行工具。规划阶段拒绝写操作。"""
    # 规划阶段物理限制：Agent根本没有写工具可调，但以防万一
    if turn <= config.planning_turns and name not in config.planning_tools:
        return False, f'规划阶段（前{config.planning_turns}轮）不允许{name}。请先输出修改计划。'

    handler = TOOL_REGISTRY.get(name)
    if not handler:
        return False, f'Unknown tool: {name}'
    try:
        return handler(args, config)
    except Exception as e:
        return False, f'Tool error: {type(e).__name__}: {e}'
