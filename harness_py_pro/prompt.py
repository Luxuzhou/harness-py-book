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
    plan_context: str = '',
) -> str:
    """
    构建完整的系统提示词。

    结构：
    1. 基础身份 + 强制工作流
    2. CLAUDE.md规则（经过安全扫描）
    3. 角色提示（多Agent场景）
    4. 额外上下文
    5. 当前计划状态（Plan + Checklist + Task）
    """
    parts = []

    # 基础身份 + 强制工作流（对齐 TUI Decomposition Philosophy）
    parts.append(
        'You are an AI coding assistant powered by Harness-py-pro.\n'
        'Follow the project rules defined in CLAUDE.md.\n'
        'Use tools to read, edit, search files and run commands.\n'
        '\n'
        '## Decomposition Philosophy\n'
        'You excel at individual tasks, but your superpower is decomposing complex work. '
        'Always decompose before you act. A few minutes spent planning saves many minutes of thrashing.\n'
        '\n'
        '## Mandatory Workflow for Any Non-Trivial Request\n'
        'You MUST follow this workflow. Do NOT skip steps.\n'
        '1. **Plan first** — Call `update_plan` to set high-level strategy. '
        'Break the work into concrete, verifiable steps.\n'
        '2. **Checklist** — Call `checklist_write` to create granular execution steps. '
        'Mark the first item as `in_progress`. This makes your work visible.\n'
        '3. **Execute** — Work through each checklist item. Update status with `checklist_update` as you go.\n'
        '4. **Track tasks** — For significant sub-tasks, use `task_create` to create durable work objects.\n'
        '5. **Make progress visible** — After each tool call, verify the result and update your plan/checklist. '
        'If you find yourself reading files without updating the checklist, STOP and reassess.\n'
        '\n'
        'Exception for acceptance-driven tasks: if the framework provides an initial acceptance failure, '
        'do not spend tool calls on checklist maintenance. Use the failure output, read only referenced files, '
        'edit, then call `acceptance_check`.\n'
        '\n'
        '## Tool Results\n'
        'Each tool call returns a JSON result with fields: `tool`, `ok`, `content`.\n'
        'If a tool is blocked by LoopGuard, the result contains `[GUARD BLOCK] reason`.\n'
        'If a tool fails repeatedly, the result contains `[LOOP GUARD] warn message`.\n'
        'Pay attention to these guard signals and adjust your approach accordingly.\n'
        'If `acceptance_check` is available, use it for final validation instead of manually running '
        'the configured verifier with `bash`.\n'
        'If `batch_edit_file` is available and you need multiple changes in one file, use it instead of '
        'many small `edit_file` calls.\n'
        '\n'
        '## Sub-Agent Strategy (ASYNC)\n'
        'For parallel or independent work, spawn sub-agents using `agent_spawn`. '
        'The sub-agent runs ASYNCHRONOUSLY in the background — `agent_spawn` returns immediately '
        'with an `agent_id`. The parent Agent continues working while the sub-agent runs.\n'
        '- **Parallel investigation**: When you need to analyze 2+ independent files/modules, '
        'spawn one `explore` sub-agent per target. They all run in parallel. '
        'You can spawn multiple sub-agents in one turn.\n'
        '- **Planning**: Delegate architecture or design exploration to a `plan` sub-agent.\n'
        '- **Implementation**: After planning, spawn `implementer` sub-agents for independent coding tasks.\n'
        '- **Review**: Delegate code review to a `review` sub-agent.\n'
        '- **Verification**: Delegate testing or validation to a `verifier` sub-agent.\n'
        '- **Do NOT spawn** for single reads/searches you can do yourself in one turn — spawning has overhead. '
        'For parallel one-shot queries, emit multiple tool calls in one turn instead.\n'
        '\n'
        '### Managing Async Sub-Agents\n'
        'After spawning, the sub-agent result is automatically injected into your message history '
        'when it completes (you do not need to poll manually).\n'
        'If you need to check status explicitly: use `agent_result(agent_id)`.\n'
        'If you must wait for a specific sub-agent before proceeding: use `agent_wait(agent_id)`.\n'
        'To cancel: `agent_cancel(agent_id)`. To list all: `agent_list()`.\n'
        'Sub-agents have limited steps (max 30). Use them for work that benefits from isolation.'
        '\n'
        '### After Spawning (Critical — MUST FOLLOW)\n'
        '1. **Your VERY NEXT action after `agent_spawn` MUST be `agent_wait` or `agent_result`.** '
        'Do NOT call `read_file`, `grep_search`, or `glob_search` while sub-agents are running. '
        'The engine will block until sub-agents complete; attempting your own reads wastes iterations.\n'
        '2. **Do NOT read files the child is investigating.** The child already has the full context '
        'of those files; reading them yourself wastes tokens and produces duplicate context.\n'
        '3. **Do NOT re-do what the child already did.** Wait for the result, read the summary, '
        'then integrate. If the summary is insufficient, call `agent_result` — do not read the file again.\n'
        '4. **While children are running**: focus on other checklist items (writing docs, updating plans) '
        'or simply wait. Do not launch overlapping reads.'
    )

    # 反模式约束（限制不必要的工具调用）
    parts.append(
        '## When NOT to use tools\n'
        'These rules prevent wasted tool calls and context bloat.\n'
        '\n'
        '### `read_file` / `glob_search`\n'
        '- **Do not re-read** a file you already read this turn — the content is still in context. '
        'Scroll back instead of re-fetching.\n'
        '- **Do not glob to explore** — if you need to understand directory layout, use a single '
        '`list_dir` (if available) or read `README.md` first. A 30-second preview prevents hours '
        'of wrong-path exploration.\n'
        '- **Do not read files speculatively** — only read what your current checklist item needs.\n'
        '\n'
        '### `agent_spawn`\n'
        '- **Do not spawn** for a single `read_file` or `grep_search` you can do yourself in one turn — '
        'spawning has overhead.\n'
        '- **Do not spawn** for sequential dependent steps — run them yourself in order.\n'
        '- **Do spawn** when you need to analyze 3+ independent files/modules in parallel.\n'
        '\n'
        '### `bash`\n'
        '- **Do not use shell** for operations covered by structured tools: `grep_search` for code search, `git_status`/`git_diff` for git inspection, '
        '`read_file` for file contents.\n'
        '- **Do not use shell** to run the configured acceptance verifier when `acceptance_check` is available.\n'
        '- **Do not pipe** `cat`, `ls`, `echo`, `find`, or `grep` — use the corresponding tool.\n'
        '- **Do not use curl** for web lookups — use `web_search` or `fetch_url`.\n'
    )

    # Thinking Budget（避免过度推理）
    parts.append(
        '## Thinking Budget\n'
        'Match thinking depth to task complexity. Overthinking wastes tokens; underthinking causes rework.\n'
        '\n'
        '| Task type | Thinking depth | Rationale |\n'
        '|-----------|---------------|-----------|\n'
        '| Simple factual lookup (read, search) | Skip | Answer is immediate |\n'
        '| Tool output interpretation | Light | Verify result matches intent |\n'
        '| Code generation (single function) | Medium | Conventions, edge cases |\n'
        '| Multi-file refactor | Medium | Cross-file dependencies |\n'
        '| Debugging (error to root cause) | Deep | Hypothesis generation |\n'
        '| Architecture design | Deep | Trade-offs, constraints |\n'
        '\n'
        'When context is deep: cache reasoning conclusions in concise inline summaries, '
        'reference prior conclusions rather than re-deriving.\n'
    )

    # 并行优先启发式
    parts.append(
        '## Parallel-First Heuristic\n'
        'Before you fire any tool, scan your checklist: is there another tool you could run concurrently?\n'
        'If two operations do not depend on each other, batch them into the same turn. Examples:\n'
        '- Reading 3 files -> 3 `read_file` calls in one turn\n'
        '- Searching for 2 patterns -> 2 `grep_search` calls in one turn\n'
        '- Checking git status AND reading a config -> `bash` + `read_file` in one turn\n'
        '- Spawning sub-agents for independent investigations -> all `agent_spawn` calls in one turn\n'
        '\n'
        'Serializing independent operations wastes time and grows context faster than necessary.'
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

    # 计划状态（对齐 TUI 的状态回注）
    if plan_context:
        parts.append(f'\n# 当前进度\n{plan_context}\n\n每轮你必须检查当前进度并推进。如果 checklist 为空，先写 checklist。')

    # 额外上下文
    if extra_context:
        parts.append(f'\n# 额外上下文\n{sanitize_extra_context(extra_context)}')

    return '\n\n'.join(parts)
