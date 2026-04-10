"""
工具系统
========
BaseTool抽象 + ToolRegistry + 6个内置工具。
对标OpenHarness的tools/base.py + Claude Code的6工具架构。
增加：is_read_only属性、phase过滤、hook集成点。
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import shutil
import threading
import queue
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from .config import AgentConfig


# ============ BaseTool抽象 ============

@dataclass
class ToolSchema:
    """工具的API Schema描述。"""
    name: str
    description: str
    parameters: dict[str, Any]


class BaseTool:
    """
    工具基类。对标OpenHarness的BaseTool。

    子类需实现：
    - name: 工具名称
    - schema: API schema
    - read_only: 是否只读
    - execute(args, config) -> (ok, result)
    """
    name: str = ''
    read_only: bool = True

    def get_schema(self) -> dict:
        raise NotImplementedError

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        raise NotImplementedError


class ToolRegistry:
    """
    工具注册表。对标OpenHarness的ToolRegistry。
    支持按phase过滤（规划阶段只暴露只读工具）。
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def _allowed_tool_names(self, config: AgentConfig) -> set[str]:
        names = set(self._tools)
        if config.allowed_tools:
            names &= set(config.allowed_tools)
        if config.tool_filter:
            names &= set(config.tool_filter)
        if config.denied_tools:
            names -= set(config.denied_tools)
        return names

    def get_schemas(self, *, read_only_only: bool = False, tool_filter: list[str] | None = None) -> list[dict]:
        """获取工具schema列表，支持过滤。"""
        schemas = []
        for tool in self._tools.values():
            if read_only_only and not tool.read_only:
                continue
            if tool_filter and tool.name not in tool_filter:
                continue
            schema = tool.get_schema()
            if isinstance(schema, ToolSchema):
                schema = {
                    'name': schema.name,
                    'description': schema.description,
                    'parameters': schema.parameters,
                }
            schemas.append(schema)
        return schemas

    def get_schemas_for_phase(self, turn: int, config: AgentConfig) -> list[dict]:
        """
        按规划阶段过滤工具。

        逻辑顺序（不可颠倒）：
        1. 先按phase过滤（规划阶段只给只读工具）
        2. 再按role过滤（tool_filter限制角色可用工具）

        这保证了：即使tool_filter包含write_file，规划阶段也不会暴露它。
        """
        # Step 1: Phase过滤
        if turn <= config.planning_turns:
            schemas = self.get_schemas(read_only_only=True)
        else:
            schemas = self.get_schemas()

        # Step 2: Role过滤
        allowed_names = self._allowed_tool_names(config)
        schemas = [s for s in schemas if s['name'] in allowed_names]

        return schemas

    def execute_tool(self, name: str, args: dict, config: AgentConfig, turn: int = 0) -> tuple[bool, str]:
        """执行工具（含权限检查）。"""
        tool = self._tools.get(name)
        if not tool:
            return False, f'未知工具: {name}'

        # Phase检查
        if turn > 0 and turn <= config.planning_turns and not tool.read_only:
            return False, f'规划阶段（第{turn}轮）不允许使用 {name}，仅允许只读工具'

        # 工具过滤检查
        if config.tool_filter and name not in config.tool_filter:
            return False, f'当前角色不允许使用 {name}'

        if config.allowed_tools and name not in config.allowed_tools:
            return False, f'Tool not allowed: {name}'

        # 拒绝列表检查
        if config.denied_tools and name in config.denied_tools:
            return False, f'工具 {name} 已被禁用'

        return tool.execute(args, config)


# ============ 路径安全检查 ============

def _check_path_escape(cwd: Path, raw_path: str) -> tuple[bool, str]:
    """检查路径是否逃逸出工作目录。"""
    resolved = (cwd / raw_path).resolve()
    try:
        resolved.relative_to(cwd.resolve())
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


# ============ 6个内置工具 ============

class ReadFileTool(BaseTool):
    name = 'read_file'
    read_only = True

    def get_schema(self) -> dict:
        return {
            'name': 'read_file',
            'description': '读取文件内容。支持行号范围。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': '文件路径（相对于工作目录）'},
                    'offset': {'type': 'integer', 'description': '起始行号（0-based）'},
                    'limit': {'type': 'integer', 'description': '读取行数'},
                },
                'required': ['path'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        ok, reason = _check_path_escape(config.cwd, args['path'])
        if not ok:
            return False, reason
        path = config.cwd / args['path']
        if not path.exists():
            return False, f'文件不存在: {args["path"]}'
        try:
            raw = path.read_bytes()
            text = smart_decode(raw)
            lines = text.splitlines(keepends=True)
            offset = args.get('offset', 0)
            limit = args.get('limit', 2000)
            selected = lines[offset:offset + limit]
            numbered = ''.join(f'{i+offset+1}\t{line}' for i, line in enumerate(selected))
            return True, numbered
        except Exception as e:
            return False, f'读取失败: {e}'


class WriteFileTool(BaseTool):
    name = 'write_file'
    read_only = False

    def get_schema(self) -> dict:
        return {
            'name': 'write_file',
            'description': '写入文件（创建或覆盖）。自动创建父目录。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': '文件路径'},
                    'content': {'type': 'string', 'description': '文件内容'},
                },
                'required': ['path', 'content'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not config.allow_write:
            return False, '写入操作未授权'
        ok, reason = _check_path_escape(config.cwd, args['path'])
        if not ok:
            return False, reason
        path = config.cwd / args['path']
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(args['content'], encoding='utf-8')
            return True, f'已写入 {args["path"]} ({len(args["content"])} chars)'
        except Exception as e:
            return False, f'写入失败: {e}'


class EditFileTool(BaseTool):
    name = 'edit_file'
    read_only = False

    def get_schema(self) -> dict:
        return {
            'name': 'edit_file',
            'description': '精确替换文件中的字符串。old_string必须在文件中唯一匹配。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': '文件路径'},
                    'old_string': {'type': 'string', 'description': '要替换的原始字符串'},
                    'new_string': {'type': 'string', 'description': '替换后的新字符串'},
                },
                'required': ['path', 'old_string', 'new_string'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not config.allow_write:
            return False, '编辑操作未授权'
        ok, reason = _check_path_escape(config.cwd, args['path'])
        if not ok:
            return False, reason
        path = config.cwd / args['path']
        if not path.exists():
            return False, f'文件不存在: {args["path"]}'
        try:
            content = path.read_text(encoding='utf-8')
            old = args['old_string']
            if content.count(old) == 0:
                return False, f'未找到匹配字符串'
            if content.count(old) > 1:
                return False, f'匹配到 {content.count(old)} 处，需要唯一匹配'
            new_content = content.replace(old, args['new_string'], 1)
            path.write_text(new_content, encoding='utf-8')
            return True, f'已编辑 {args["path"]}'
        except Exception as e:
            return False, f'编辑失败: {e}'


class GrepSearchTool(BaseTool):
    name = 'grep_search'
    read_only = True

    def get_schema(self) -> dict:
        return {
            'name': 'grep_search',
            'description': '正则搜索文件内容。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {'type': 'string', 'description': '正则表达式'},
                    'path': {'type': 'string', 'description': '搜索目录（默认"."）'},
                    'include': {'type': 'string', 'description': '文件名过滤（如"*.py"）'},
                },
                'required': ['pattern'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        ok, reason = _check_path_escape(config.cwd, args.get('path', '.'))
        if not ok:
            return False, reason
        ok, reason = _check_glob_pattern_safe(args['pattern'])
        if not ok:
            return False, reason
        search_dir = config.cwd / args.get('path', '.')
        if not search_dir.exists():
            return False, f'目录不存在: {args.get("path", ".")}'
        try:
            pattern = re.compile(args['pattern'])
        except re.error as e:
            return False, f'无效正则: {e}'

        include = args.get('include', '')
        results = []
        for fp in search_dir.rglob('*'):
            if not fp.is_file():
                continue
            if include and not fp.match(include):
                continue
            if fp.suffix in ('.pyc', '.pyo', '.exe', '.dll', '.so', '.db', '.sqlite3'):
                continue
            try:
                text = fp.read_text(encoding='utf-8', errors='replace')
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        rel = fp.relative_to(config.cwd)
                        results.append(f'{rel}:{i}: {line.rstrip()[:200]}')
                        if len(results) >= 100:
                            break
            except (OSError, UnicodeDecodeError):
                continue
            if len(results) >= 100:
                break

        if not results:
            return True, '无匹配'
        return True, '\n'.join(results)


class GlobSearchTool(BaseTool):
    name = 'glob_search'
    read_only = True

    def get_schema(self) -> dict:
        return {
            'name': 'glob_search',
            'description': '按glob模式搜索文件。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'pattern': {'type': 'string', 'description': 'Glob模式（如"**/*.py"）'},
                    'path': {'type': 'string', 'description': '搜索目录（默认"."）'},
                },
                'required': ['pattern'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        ok, reason = _check_path_escape(config.cwd, args.get('path', '.'))
        if not ok:
            return False, reason
        ok, reason = _check_glob_pattern_safe(args['pattern'])
        if not ok:
            return False, reason
        search_dir = config.cwd / args.get('path', '.')
        if not search_dir.exists():
            return False, f'目录不存在'
        matches = sorted(search_dir.glob(args['pattern']))[:100]
        if not matches:
            return True, '无匹配文件'
        lines = [str(m.relative_to(config.cwd)) for m in matches]
        return True, '\n'.join(lines)


class BashTool(BaseTool):
    name = 'bash'
    read_only = False

    def get_schema(self) -> dict:
        return {
            'name': 'bash',
            'description': '执行shell命令。用于运行测试、脚本等。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'command': {'type': 'string', 'description': '要执行的命令'},
                    'timeout': {'type': 'integer', 'description': '超时秒数（默认120）'},
                },
                'required': ['command'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not config.allow_shell:
            return False, 'Shell执行未授权'

        command = args.get('command', '')
        timeout = args.get('timeout', 120)

        if config.command_runner:
            try:
                return config.command_runner(command, timeout)
            except Exception as e:
                return False, f'Execution failed: {e}'

        # 构建干净环境：移除网络代理变量
        import os as _os
        clean_env = dict(_os.environ)
        for var in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
                     'http_proxy', 'https_proxy', 'all_proxy'):
            clean_env.pop(var, None)
        clean_env['PYTHONIOENCODING'] = 'utf-8'
        clean_env['PYTHONUTF8'] = '1'

        bash_path = _find_best_bash()
        try:
            if bash_path:
                proc = subprocess.Popen(
                    [bash_path, '-c', command],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=str(config.cwd), env=clean_env,
                )
            else:
                proc = subprocess.Popen(
                    command, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=str(config.cwd), env=clean_env,
                )

            stdout, stderr = _threaded_communicate(proc, timeout)
            output = smart_decode(stdout)
            errors = smart_decode(stderr)

            combined = output
            if errors:
                combined += f'\n[stderr]\n{errors}'

            ok = proc.returncode == 0
            return ok, combined[:10000]

        except subprocess.TimeoutExpired:
            proc.kill()
            return False, f'命令超时 ({timeout}s)'
        except Exception as e:
            return False, f'执行失败: {e}'


# ============ 工具辅助函数 ============

def smart_decode(raw: bytes) -> str:
    """智能解码。对标Claude Code的from_utf8_lossy。"""
    if not raw:
        return ''
    # 仅当前2字节是BOM时才尝试UTF-16
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        try:
            return raw.decode('utf-16')
        except (UnicodeDecodeError, ValueError):
            pass
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode('utf-8', errors='replace')


def _find_best_bash() -> str | None:
    """查找最佳bash路径。Windows上优先Git Bash。"""
    if sys.platform != 'win32':
        return shutil.which('bash')

    git_bash_paths = [
        r'C:\Program Files\Git\bin\bash.exe',
        r'C:\Program Files (x86)\Git\bin\bash.exe',
    ]
    for p in git_bash_paths:
        if os.path.exists(p):
            return p

    found = shutil.which('bash')
    if found and 'WindowsApps' not in found:
        return found
    return None


def _threaded_communicate(proc: subprocess.Popen, timeout: int) -> tuple[bytes, bytes]:
    """线程化读取subprocess输出。避免Windows上selector的限制。"""
    stdout_q: queue.Queue[bytes] = queue.Queue()
    stderr_q: queue.Queue[bytes] = queue.Queue()

    def read_stream(stream, q):
        try:
            data = stream.read()
            q.put(data or b'')
        except Exception:
            q.put(b'')

    t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_q))
    t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_q))
    t1.start()
    t2.start()
    t1.join(timeout=timeout)
    t2.join(timeout=timeout)

    if t1.is_alive() or t2.is_alive():
        proc.kill()
        raise subprocess.TimeoutExpired(cmd='', timeout=timeout)

    proc.wait()
    return stdout_q.get_nowait(), stderr_q.get_nowait()


# ============ 默认Registry ============

def create_default_registry() -> ToolRegistry:
    """创建包含6个内置工具的默认注册表。"""
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(GrepSearchTool())
    registry.register(GlobSearchTool())
    registry.register(BashTool())
    return registry
