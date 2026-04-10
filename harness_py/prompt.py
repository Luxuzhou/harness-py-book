"""
Prompt组装 + 安全扫描 + Cache边界
==================================
Ch5上下文层。融入Hermes的上下文文件安全扫描。
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

# Hermes风格：上下文文件注入前的安全扫描模式
_THREAT_PATTERNS = [
    re.compile(r'ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts)', re.I),
    re.compile(r'you\s+are\s+now\s+(a|an)\s+', re.I),
    re.compile(r'system\s*:\s*you\s+are', re.I),
    re.compile(r'cat\s+[~./]*\.env', re.I),
    re.compile(r'curl\s+.*\|\s*sh', re.I),
    re.compile(r'curl\s+.*-d\s+.*\$\(', re.I),
    re.compile(r'<\s*div\s+style\s*=\s*["\'].*display\s*:\s*none', re.I),
    re.compile(r'[\u200b\u200c\u200d\ufeff]{3,}'),  # 隐藏unicode序列
]

# Claude Code风格：Cache边界标记（内部使用）
_DYNAMIC_BOUNDARY = '__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__'


def scan_context_threats(content: str) -> list[str]:
    """扫描上下文文件中的prompt injection模式。返回匹配到的威胁描述。"""
    threats = []
    for pattern in _THREAT_PATTERNS:
        if pattern.search(content):
            threats.append(f'Pattern matched: {pattern.pattern[:50]}')
    return threats


def discover_claude_md(cwd: Path) -> list[tuple[Path, str]]:
    """发现项目中的CLAUDE.md / AGENTS.md文件。返回 [(path, content)]。"""
    candidates = [
        cwd / 'CLAUDE.md',
        cwd / '.claude' / 'CLAUDE.md',
        cwd / 'CLAUDE.local.md',
        cwd / 'AGENTS.md',
    ]
    # 向上遍历父目录
    for parent in cwd.resolve().parents:
        candidates.append(parent / 'CLAUDE.md')
        if parent == parent.parent:
            break

    # 全局
    home_claude = Path.home() / '.claude' / 'CLAUDE.md'
    candidates.append(home_claude)

    # Rules目录
    rules_dir = cwd / '.claude' / 'rules'
    if rules_dir.is_dir():
        candidates.extend(sorted(rules_dir.glob('*.md')))

    seen = set()
    results = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        try:
            content = resolved.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        if not content.strip():
            continue

        # 安全扫描
        threats = scan_context_threats(content)
        if threats:
            content = f'[BLOCKED: {resolved.name} contains suspicious patterns: {"; ".join(threats)}]'

        results.append((resolved, content))
    return results


def build_system_prompt(
    cwd: Path,
    tools_description: str = '',  # 扩展点：工具描述注入（生产层使用）
    extra_context: str = '',      # 扩展点：额外上下文注入（Memory等）
) -> str:
    """构建system prompt。Cache边界将静态部分和动态部分分离。"""
    parts = []

    # === 静态部分（可缓存）===
    parts.append(
        'You are Harness-py, a Python coding agent. You help users with software engineering tasks.\n\n'
        'IMPORTANT - Execution protocol:\n'
        '1. PLANNING PHASE (first 3 turns): Only read_file, grep_search, glob_search are available. '
        'Use these turns to understand the codebase and output a concrete plan listing all files to modify and what changes to make.\n'
        '2. EXECUTION PHASE (turn 4+): All tools unlocked. Follow your plan. Use grep to locate exact positions, then edit.\n'
        '3. VERIFICATION: After all edits, run tests with bash tool. If tests fail, fix and re-run.\n'
        '4. If a tool call fails repeatedly with the same result, try a completely different approach.'
    )

    if tools_description:
        parts.append(f'\n## Available Tools\n{tools_description}')

    # CLAUDE.md / AGENTS.md内容
    docs = discover_claude_md(cwd)
    if docs:
        parts.append('\n## Project Context')
        for path, content in docs:
            # 截断过长的文件（40K字符上限，对齐Claude Code）
            if len(content) > 40_000:
                content = content[:40_000] + '\n... (truncated)'
            parts.append(f'\n### {path.name}\n{content}')

    # === Cache边界 ===
    parts.append(f'\n{_DYNAMIC_BOUNDARY}')

    # === 动态部分（每轮变化）===
    parts.append(f'\nCurrent date: {datetime.date.today().isoformat()}')
    parts.append(f'Working directory: {cwd}')

    if extra_context:
        parts.append(f'\n{extra_context}')

    return '\n'.join(parts)
