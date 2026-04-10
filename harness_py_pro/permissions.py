"""
权限系统
========
对标OpenHarness的permissions/checker + Claude Code的敏感路径保护。
提供路径级和工具级的权限检查。
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from .config import AgentConfig


# Claude Code内置的敏感路径（始终拒绝）
SENSITIVE_PATHS = [
    '~/.ssh/*',
    '~/.aws/credentials',
    '~/.azure/*',
    '~/.gnupg/*',
    '~/.docker/config.json',
    '~/.kube/config',
    '*/.env',
    '*/credentials.json',
    '*/.git/config',
]


class PermissionChecker:
    """
    权限检查器。

    三层检查：
    1. 敏感路径保护（硬编码，不可覆盖）
    2. 配置级路径限制（allowed_paths / denied_paths）
    3. 工具级权限（allowed_tools / denied_tools）
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self._expanded_sensitive = [
            p.replace('~', str(Path.home())) for p in SENSITIVE_PATHS
        ]

    def check_path(self, path: str, action: str = 'read') -> tuple[bool, str]:
        """
        检查路径访问权限。

        返回 (allowed, reason)
        """
        resolved = str((self.config.cwd / path).resolve())

        # Layer 1: 敏感路径
        for pattern in self._expanded_sensitive:
            if fnmatch.fnmatch(resolved, pattern):
                return False, f'敏感路径保护: {path}'

        # Layer 2: 配置级路径限制（读写都检查）
        resolved_path = (self.config.cwd / path).resolve()
        if self.config.allowed_paths:
            allowed = False
            for ap in self.config.allowed_paths:
                try:
                    resolved_path.relative_to((self.config.cwd / ap).resolve())
                    allowed = True
                    break
                except ValueError:
                    continue
            if not allowed:
                return False, f'路径不在允许范围内: {path}'

        if self.config.denied_paths:
            for dp in self.config.denied_paths:
                try:
                    resolved_path.relative_to((self.config.cwd / dp).resolve())
                    return False, f'路径已被禁止: {path}'
                except ValueError:
                    continue

        return True, ''

    def check_tool(self, tool_name: str) -> tuple[bool, str]:
        """检查工具使用权限。"""
        if tool_name == 'bash' and not self.config.allow_shell:
            return False, 'Shell execution disabled'

        if tool_name in ('write_file', 'edit_file') and not self.config.allow_write:
            return False, f'Write access disabled: {tool_name}'

        if self.config.denied_tools and tool_name in self.config.denied_tools:
            return False, f'工具已被禁用: {tool_name}'

        if self.config.allowed_tools and tool_name not in self.config.allowed_tools:
            return False, f'工具未在允许列表中: {tool_name}'

        if self.config.tool_filter and tool_name not in self.config.tool_filter:
            return False, f'工具未在角色工具列表中: {tool_name}'

        return True, ''
