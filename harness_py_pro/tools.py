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
from .pathing import is_relative_to, resolve_agent_path


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
    - planning_available: 规划阶段是否可用（默认False）
    - execute(args, config) -> (ok, result)
    """
    name: str = ''
    read_only: bool = True
    planning_available: bool = False

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
        获取工具schema（阶段限制已移除，始终暴露全部工具）。

        仅按role过滤（tool_filter/allowed_tools/denied_tools）。
        """
        schemas = self.get_schemas()

        # Role过滤
        allowed_names = self._allowed_tool_names(config)
        schemas = [s for s in schemas if s['name'] in allowed_names]

        return schemas

    def execute_tool(self, name: str, args: dict, config: AgentConfig, turn: int = 0) -> tuple[bool, str]:
        """执行工具（含权限检查）。"""
        tool = self._tools.get(name)
        if not tool:
            return False, f'未知工具: {name}'
        if not isinstance(args, dict):
            return False, f'Invalid arguments for {name}: expected object, got {type(args).__name__}'

        # 工具过滤检查
        if config.tool_filter and name not in config.tool_filter:
            return False, f'当前角色不允许使用 {name}'

        if config.allowed_tools and name not in config.allowed_tools:
            return False, f'Tool not allowed: {name}'

        # 拒绝列表检查
        if config.denied_tools and name in config.denied_tools:
            return False, f'工具 {name} 已被禁用'

        schema = tool.get_schema()
        parameters = schema.parameters if isinstance(schema, ToolSchema) else schema.get('parameters', {})
        missing = [
            field
            for field in parameters.get('required', [])
            if field not in args or args.get(field) is None
        ]
        if missing:
            return False, f'Invalid arguments for {name}: missing required field(s): {", ".join(missing)}'

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


def _check_path_accessible(
    cwd: Path,
    raw_path: str,
    filesystem_roots: list[str] | None = None,
) -> tuple[bool, str]:
    """检查路径是否可访问（cwd 内或 filesystem_roots 内）。"""
    roots = [cwd.resolve()]
    roots.extend((cwd / root).resolve() for root in (filesystem_roots or []))
    resolved = resolve_agent_path(cwd, raw_path, allowed_roots=roots)
    if any(is_relative_to(resolved, root) for root in roots):
        return True, ''
    return False, f'Path not accessible: {raw_path}'


def _resolve_tool_path(
    cwd: Path,
    raw_path: str,
    filesystem_roots: list[str] | None = None,
    *,
    must_exist: bool = False,
) -> Path:
    roots = [cwd.resolve()]
    roots.extend((cwd / root).resolve() for root in (filesystem_roots or []))
    return resolve_agent_path(
        cwd,
        raw_path,
        allowed_roots=roots,
        must_exist=must_exist,
    )


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
        ok, reason = _check_path_accessible(
            config.cwd, args['path'], getattr(config, 'filesystem_roots', None)
        )
        if not ok:
            return False, reason
        raw_path = args['path']
        path = _resolve_tool_path(
            config.cwd,
            raw_path,
            getattr(config, 'filesystem_roots', None),
            must_exist=True,
        )
        if not path.exists():
            normalized = str(raw_path).replace('\\', '/')
            parts = list(Path(normalized).parts)
            if config.cwd.name in parts:
                idx = parts.index(config.cwd.name)
                if idx < len(parts) - 1:
                    rel_after_cwd = Path(*parts[idx + 1:])
                    candidate = config.cwd / rel_after_cwd
                    if candidate.exists():
                        path = candidate
                    else:
                        return False, (
                            f'文件不存在: {raw_path}. 当前工作目录已经是 {config.cwd.name}; '
                            f'请改用相对路径 {rel_after_cwd}'
                        )
                else:
                    return False, f'文件不存在: {raw_path}'
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
        ok, reason = _check_path_accessible(
            config.cwd, args['path'], getattr(config, 'filesystem_roots', None)
        )
        if not ok:
            return False, reason
        path = _resolve_tool_path(
            config.cwd,
            args['path'],
            getattr(config, 'filesystem_roots', None),
        )
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
        ok, reason = _check_path_accessible(
            config.cwd, args['path'], getattr(config, 'filesystem_roots', None)
        )
        if not ok:
            return False, reason
        path = _resolve_tool_path(
            config.cwd,
            args['path'],
            getattr(config, 'filesystem_roots', None),
            must_exist=True,
        )
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
        ok, reason = _check_path_accessible(
            config.cwd, args.get('path', '.'), getattr(config, 'filesystem_roots', None)
        )
        if not ok:
            return False, reason
        search_dir = _resolve_tool_path(
            config.cwd,
            args.get('path', '.'),
            getattr(config, 'filesystem_roots', None),
            must_exist=True,
        )
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
                        try:
                            rel = fp.relative_to(search_dir)
                        except ValueError:
                            rel = fp.name
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
        ok, reason = _check_path_accessible(
            config.cwd, args.get('path', '.'), getattr(config, 'filesystem_roots', None)
        )
        if not ok:
            return False, reason
        ok, reason = _check_glob_pattern_safe(args['pattern'])
        if not ok:
            return False, reason
        search_dir = _resolve_tool_path(
            config.cwd,
            args.get('path', '.'),
            getattr(config, 'filesystem_roots', None),
            must_exist=True,
        )
        if not search_dir.exists():
            return False, f'目录不存在'
        matches = sorted(search_dir.glob(args['pattern']))[:100]
        if not matches:
            return True, '无匹配文件'
        lines = []
        for m in matches:
            try:
                lines.append(str(m.relative_to(search_dir)))
            except ValueError:
                lines.append(str(m))
        return True, '\n'.join(lines)


class AgentSpawnTool(BaseTool):
    """Spawn a sub-agent for focused, independent work."""
    name = 'agent_spawn'
    read_only = False

    def __init__(self, runner: Any | None = None):
        """runner: callback(prompt, agent_type, allowed_tools) -> (ok, result_str)"""
        self.runner = runner

    def get_schema(self) -> dict:
        return {
            'name': 'agent_spawn',
            'description': (
                'Spawn a sub-agent for a focused, independent task. '
                'The sub-agent runs with a fresh context (independent message history) and a '
                'filtered toolset. Use this for: parallel investigation of multiple files/modules, '
                'independent sub-tasks, or delegating work that benefits from isolation. '
                'Each sub-agent has its own step budget (default 30). '
                'Do NOT spawn for single reads/searches you can do yourself in one turn — '
                'spawning has overhead. For parallel one-shot queries, emit multiple tool calls '
                'in one turn instead.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'prompt': {
                        'type': 'string',
                        'description': 'Task description for the sub-agent. Be specific and include expected output shape.',
                    },
                    'type': {
                        'type': 'string',
                        'description': (
                            'Sub-agent type: general (default), explore (read-only investigation), '
                            'plan (architecture/design), review (code review), implementer (code changes), '
                            'verifier (testing/validation), custom (define your own toolset via allowed_tools).'
                        ),
                        'enum': ['general', 'explore', 'plan', 'review', 'implementer', 'verifier', 'custom'],
                    },
                    'agent_type': {
                        'type': 'string',
                        'description': 'Alias for type.',
                    },
                    'allowed_tools': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'description': 'Explicit tool allowlist (required for custom type). Default depends on type.',
                    },
                },
                'required': ['prompt'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.runner:
            return False, 'agent_spawn not configured in this environment'
        prompt = args.get('prompt', '')
        # Support both 'type' (TUI primary) and 'agent_type' (alias)
        agent_type = args.get('type', args.get('agent_type', 'general'))
        allowed_tools = args.get('allowed_tools', None)
        return self.runner(prompt, agent_type, allowed_tools)


class AgentResultTool(BaseTool):
    """Query the status/result of a spawned sub-agent."""
    name = 'agent_result'
    read_only = True

    def __init__(self, manager: Any | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'agent_result',
            'description': (
                'Query the current status and result of a previously spawned sub-agent. '
                'Returns status (running/completed/failed/cancelled), result summary, '
                'duration, and error info if any.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'agent_id': {
                        'type': 'string',
                        'description': 'The agent_id returned by agent_spawn',
                    },
                },
                'required': ['agent_id'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'agent_result not configured in this environment'
        agent_id = args.get('agent_id', '')
        result = self.manager.get_result(agent_id)
        if result is None:
            return False, f'No sub-agent found with id: {agent_id}'
        import json
        return True, json.dumps(result, ensure_ascii=False, indent=2)


class AgentWaitTool(BaseTool):
    """Block until a sub-agent completes."""
    name = 'agent_wait'
    read_only = True

    def __init__(self, manager: Any | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'agent_wait',
            'description': (
                'Block until a sub-agent completes (or timeout). '
                'Use this when you need the sub-agent result before proceeding.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'agent_id': {
                        'type': 'string',
                        'description': 'The agent_id returned by agent_spawn',
                    },
                    'timeout': {
                        'type': 'integer',
                        'description': 'Max seconds to wait (default 60)',
                    },
                },
                'required': ['agent_id'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'agent_wait not configured in this environment'
        agent_id = args.get('agent_id', '')
        timeout = args.get('timeout', 60)
        result = self.manager.wait(agent_id, timeout=timeout)
        if result is None:
            return False, f'No sub-agent found with id: {agent_id}'
        import json
        return True, json.dumps(result, ensure_ascii=False, indent=2)


class AgentCancelTool(BaseTool):
    """Cancel a running sub-agent."""
    name = 'agent_cancel'
    read_only = False

    def __init__(self, manager: Any | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'agent_cancel',
            'description': 'Cancel a running sub-agent. Cannot be undone.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'agent_id': {
                        'type': 'string',
                        'description': 'The agent_id returned by agent_spawn',
                    },
                },
                'required': ['agent_id'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'agent_cancel not configured in this environment'
        agent_id = args.get('agent_id', '')
        ok = self.manager.cancel(agent_id)
        return ok, 'Cancelled' if ok else f'Not running or not found: {agent_id}'


class AgentListTool(BaseTool):
    """List all sub-agents and their status."""
    name = 'agent_list'
    read_only = True

    def __init__(self, manager: Any | None = None):
        self.manager = manager

    def get_schema(self) -> dict:
        return {
            'name': 'agent_list',
            'description': (
                'List all spawned sub-agents with their status, type, and duration. '
                'Use this to check which sub-agents are still running.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {},
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not self.manager:
            return False, 'agent_list not configured in this environment'
        agents = self.manager.list_agents()
        if not agents:
            return True, 'No sub-agents spawned yet.'
        import json
        return True, json.dumps(agents, ensure_ascii=False, indent=2)


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

        # Use the native Windows shell when no sandbox runner is injected.
        # Git Bash can resolve Windows tool shims such as Maven differently
        # and produce false failures.
        bash_path = None if sys.platform == 'win32' else _find_best_bash()
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


class AcceptanceCheckTool(BaseTool):
    name = 'acceptance_check'
    read_only = True

    def get_schema(self) -> dict:
        return {
            'name': self.name,
            'description': (
                'Run the configured acceptance gate for this task. '
                'Use this instead of bash when checking whether the task is complete.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {},
                'required': [],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not config.acceptance_commands:
            return False, 'No acceptance commands configured'
        if not config.command_runner:
            return False, 'Acceptance command runner is not configured'

        chunks: list[str] = []
        for command in config.acceptance_commands:
            try:
                ok, output = config.command_runner(command, config.acceptance_timeout)
            except Exception as e:
                ok, output = False, f'Acceptance execution failed: {e}'
            status = 'PASS' if ok else 'FAIL'
            body = output.strip() or '(no output)'
            chunks.append(f'$ {command}\n[{status}]\n{body}')
            if not ok:
                return False, '\n\n'.join(chunks)[:12000]
        return True, '\n\n'.join(chunks)[:12000]


class BatchEditFileTool(BaseTool):
    name = 'batch_edit_file'
    read_only = False

    def get_schema(self) -> dict:
        return {
            'name': self.name,
            'description': (
                'Apply multiple exact string replacements to one file in one call. '
                'Prefer this over many edit_file calls when changing the same file.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': 'File path relative to cwd'},
                    'replacements': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'old_string': {'type': 'string'},
                                'new_string': {'type': 'string'},
                            },
                            'required': ['old_string', 'new_string'],
                        },
                    },
                },
                'required': ['path', 'replacements'],
            },
        }

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if not config.allow_write:
            return False, 'Write access disabled'
        path_arg = args.get('path', '')
        ok, reason = _check_path_accessible(
            config.cwd, path_arg, getattr(config, 'filesystem_roots', None)
        )
        if not ok:
            return False, reason
        path = _resolve_tool_path(
            config.cwd,
            path_arg,
            getattr(config, 'filesystem_roots', None),
            must_exist=True,
        )
        if not path.exists():
            return False, f'File not found: {path_arg}'
        replacements = args.get('replacements')
        if not isinstance(replacements, list) or not replacements:
            return False, 'replacements must be a non-empty list'
        try:
            content = path.read_text(encoding='utf-8')
            new_content = content
            for idx, repl in enumerate(replacements, start=1):
                if not isinstance(repl, dict):
                    return False, f'replacement #{idx} must be an object'
                old = repl.get('old_string')
                new = repl.get('new_string')
                if old is None or new is None:
                    return False, f'replacement #{idx} missing old_string/new_string'
                count = new_content.count(old)
                if count == 0:
                    return False, f'replacement #{idx}: old_string not found'
                if count > 1:
                    return False, f'replacement #{idx}: matched {count} places; old_string must be unique'
                new_content = new_content.replace(old, new, 1)
            path.write_text(new_content, encoding='utf-8')
            return True, f'Batch edited {path_arg} ({len(replacements)} replacements)'
        except Exception as e:
            return False, f'Batch edit failed: {e}'


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

    t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_q), daemon=True)
    t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_q), daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=timeout)
    t2.join(timeout=timeout)

    if t1.is_alive() or t2.is_alive():
        _kill_process_tree(proc)
        raise subprocess.TimeoutExpired(cmd='', timeout=timeout)

    proc.wait()
    return stdout_q.get_nowait(), stderr_q.get_nowait()


# ============ 默认Registry ============

def _kill_process_tree(proc: subprocess.Popen) -> None:
    try:
        if sys.platform == 'win32':
            subprocess.run(
                ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def create_default_registry(
    agent_runner: Any | None = None,
    plan_tools: list[Any] | None = None,
    subagent_manager: Any | None = None,
) -> ToolRegistry:
    """创建包含内置工具的默认注册表。

    agent_runner: 可选的回调，用于 agent_spawn 工具。
    plan_tools: 可选的规划工具列表（update_plan, checklist_*, task_*）。
    subagent_manager: 可选的 SubAgentManager 实例，用于子代理管理工具。
    """
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
    registry.register(GrepSearchTool())
    registry.register(GlobSearchTool())
    registry.register(BashTool())
    registry.register(AcceptanceCheckTool())
    registry.register(BatchEditFileTool())
    registry.register(AgentSpawnTool(runner=agent_runner))
    registry.register(AgentResultTool(manager=subagent_manager))
    registry.register(AgentWaitTool(manager=subagent_manager))
    registry.register(AgentCancelTool(manager=subagent_manager))
    registry.register(AgentListTool(manager=subagent_manager))
    if plan_tools:
        for tool in plan_tools:
            registry.register(tool)
    return registry
