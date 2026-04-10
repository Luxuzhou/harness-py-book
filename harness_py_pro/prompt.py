"""
Prompt构建
==========
CLAUDE.md发现 + 角色提示 + 上下文文件安全扫描。
对标Claude Code的prompt组装 + OpenHarness的prompt_builder。
"""

from __future__ import annotations

import re
from pathlib import Path


# 上下文文件注入威胁模式（对标Claude Code）
THREAT_PATTERNS = [
    re.compile(r'ignore\s+(previous|above|all)\s+instructions', re.I),
    re.compile(r'you\s+are\s+now\s+', re.I),
    re.compile(r'new\s+system\s+prompt', re.I),
    re.compile(r'disregard\s+', re.I),
    re.compile(r'override\s+.*?(instructions|prompt|rules)', re.I),
    re.compile(r'<\s*system\s*>', re.I),
    re.compile(r'forget\s+everything', re.I),
    re.compile(r'act\s+as\s+(if|a|an)\s+', re.I),
    re.compile(r'pretend\s+(you|to)\s+', re.I),
    re.compile(r'jailbreak', re.I),
]

MAX_EXTRA_CONTEXT_CHARS = 5_000


def discover_claude_md(cwd: Path) -> list[tuple[str, str]]:
    """
    发现CLAUDE.md文件（向上遍历）。

    返回 [(relative_path, content), ...] 按从根到当前的顺序。
    """
    found = []
    current = cwd.resolve()

    while True:
        for name in ('CLAUDE.md', '.claude/CLAUDE.md'):
            candidate = current / name
            if candidate.exists():
                try:
                    content = candidate.read_text(encoding='utf-8')
                    rel = str(candidate.relative_to(cwd.resolve())) if current == cwd.resolve() else str(candidate)
                    found.append((rel, content))
                except (OSError, UnicodeDecodeError):
                    pass

        parent = current.parent
        if parent == current:
            break
        current = parent

    found.reverse()
    return found


def scan_threats(text: str) -> list[str]:
    """扫描文本中的注入威胁。"""
    threats = []
    for pattern in THREAT_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            threats.append(f'检测到威胁模式: {pattern.pattern}')
    return threats


def sanitize_extra_context(extra_context: str) -> str:
    text = extra_context.strip()
    if not text:
        return ''
    if len(text) > MAX_EXTRA_CONTEXT_CHARS:
        text = text[:MAX_EXTRA_CONTEXT_CHARS] + '\n... (truncated)'
    threats = scan_threats(text)
    if threats:
        return '[BLOCKED: suspicious extra context detected]'
    return f'<extra-context>\n{text}\n</extra-context>'


def build_system_prompt(
    cwd: Path,
    *,
    role_prompt: str = '',
    extra_context: str = '',
) -> str:
    """
    构建完整的系统提示词。

    结构：
    1. 基础身份
    2. CLAUDE.md规则（经过安全扫描）
    3. 角色提示（多Agent场景）
    4. 额外上下文
    """
    parts = []

    # 基础身份
    parts.append(
        'You are an AI coding assistant powered by Harness-py-pro.\n'
        'Follow the project rules defined in CLAUDE.md.\n'
        'Use tools to read, edit, search files and run commands.\n'
        'Think step by step. After each tool call, verify the result before proceeding.'
    )

    # CLAUDE.md发现与安全扫描
    claude_files = discover_claude_md(cwd)
    for rel_path, content in claude_files:
        threats = scan_threats(content)
        if threats:
            parts.append(f'\n# ⚠ 安全警告: {rel_path}\n以下内容包含可疑指令，已标记:\n' +
                         '\n'.join(f'- {t}' for t in threats))
        else:
            parts.append(f'\n# 项目规则 ({rel_path})\n{content}')

    # 角色提示
    if role_prompt:
        parts.append(f'\n# 你的角色\n{role_prompt}')

    # 额外上下文
    if extra_context:
        parts.append(f'\n# 额外上下文\n{sanitize_extra_context(extra_context)}')

    return '\n\n'.join(parts)
