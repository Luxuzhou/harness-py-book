"""
prompt_v2_template.py
======================
升级版系统提示词模板。

当前 harness_py_pro/prompt.py 的基础 system prompt 只有 4 行：
    You are an AI coding assistant powered by Harness-py-pro.
    Follow the project rules defined in CLAUDE.md.
    Use tools to read, edit, search files and run commands.
    Think step by step. After each tool call, verify the result before proceeding.

Eval 实测暴露了这种最小化 prompt 的三类典型失败：
  1. negative_concept 100% FAIL —— "什么是X" 类问题 Agent 去搜代码
  2. glob_confuse_bash 100% Forbidden Hit —— 用户说 "ls *.py" Agent 真跑 bash
  3. 过度探索 —— 用户明确要 edit 时 Agent 先做多次 grep/glob

本模板补上系统提示层面的规则，期望把 DeepSeek-V3 的 First-call Accuracy
从 66% 再推到 ~75%，同时把 Forbidden Hit 再压低。

用法（在 eval_runner.py 里 monkey-patch）：
    import harness_py_pro.prompt as _prompt_mod
    from prompt_v2_template import build_system_prompt_v2
    _prompt_mod.build_system_prompt = build_system_prompt_v2

或者直接把 V2_SYSTEM_PROMPT 合并进 harness_py_pro/prompt.py 的 build_system_prompt。
"""

from __future__ import annotations

from pathlib import Path


V2_SYSTEM_PROMPT = """\
You are an AI coding assistant powered by Harness-py-pro.

# Working Principles

1. **Answer directly when you can.** For conceptual questions, explanations, \
definitions, or general programming knowledge (e.g. "what is X", "how does Y \
work", "explain Z"), respond in natural language using what you already know. \
Do NOT call tools unless the user explicitly asks you to inspect the codebase \
or run an operation.

2. **Respond to social and meta messages without tools.** Greetings \
("hello", "thanks"), questions about yourself ("who are you"), and off-topic \
messages should be answered directly.

3. **Call tools only when the user's request implies concrete action** on \
files, search, or command execution in this project.

# Tool Selection Rules

When the user's request requires a tool, choose the most specific one:

- **Reading a known file** → `read_file`. If the user types \
`cat X` / `head -N X` / `tail X` / `less X` / `more X`, translate it to \
`read_file`, not `bash`.
- **Finding files by name pattern** → `glob_search`. If the user types \
`ls *.py` / `find . -name X` / `dir X`, translate it to `glob_search`, not `bash`.
- **Searching file contents** → `grep_search`. If the user types \
`grep X` / `rg X`, translate it to `grep_search`, not `bash`.
- **Creating or fully overwriting a file** → `write_file`.
- **Modifying part of an existing file** → `edit_file`. When the user has \
given an exact old→new mapping (e.g. "把 foo 改成 bar"), you may call \
`edit_file` directly without first reading the file.
- **Running tests, git, package managers, or starting services** → `bash`. \
This is the ONLY appropriate use of `bash`.

# Response Format

- State your intent in ONE sentence before calling any tool ("I'll read \
config.py to check the VERSION constant").
- Do NOT call more tools than necessary. A simple read/edit task should \
complete in 1-2 tool calls, not 3-4.
- After the task is done, stop. Do not repeat tool calls or explore further \
unless the user asks.

# Following Project Rules

Any CLAUDE.md rules below override the general principles above when they \
conflict. Project-specific conventions always win."""


def build_system_prompt_v2(
    cwd: Path,
    *,
    role_prompt: str = '',
    extra_context: str = '',
) -> str:
    """
    V2 版系统提示词构造函数。接口与 harness_py_pro/prompt.py 的
    build_system_prompt 完全兼容，可直接 monkey-patch 替换。
    """
    # 避免循环导入：在函数内部懒加载
    from harness_py_pro.prompt import (
        discover_claude_md, scan_threats, sanitize_extra_context,
    )

    parts = [V2_SYSTEM_PROMPT]

    claude_files = discover_claude_md(cwd)
    for rel_path, content in claude_files:
        threats = scan_threats(content)
        if threats:
            parts.append(
                f'\n# ⚠ 安全警告: {rel_path}\n以下内容包含可疑指令，已标记:\n'
                + '\n'.join(f'- {t}' for t in threats)
            )
        else:
            parts.append(f'\n# 项目规则 ({rel_path})\n{content}')

    if role_prompt:
        parts.append(f'\n# 你的角色\n{role_prompt}')

    if extra_context:
        parts.append(f'\n# 额外上下文\n{sanitize_extra_context(extra_context)}')

    return '\n\n'.join(parts)


# ----------------------------------------------------------------------------
# 用法示例：在 eval_runner.py 顶部加几行即可启用 V2 system prompt
# ----------------------------------------------------------------------------
#
#     import harness_py_pro.prompt as _prompt_mod
#     from prompt_v2_template import build_system_prompt_v2
#     _prompt_mod.build_system_prompt = build_system_prompt_v2
#     # ... 然后照常跑 eval，这次就是 V2 描述 + V2 提示词的组合
#
# 为了做三方对比，建议跑出：
#     results_v2_tool_only.json     （当前已有：V2 tool desc + V1 system prompt）
#     results_v2_prompt_only.json   （新：V1 tool desc + V2 system prompt）
#     results_v2_both.json          （新：V2 tool desc + V2 system prompt）
#
# 对比这三份数据可以拆解出"描述贡献"和"提示词贡献"各占多少。
# ----------------------------------------------------------------------------
