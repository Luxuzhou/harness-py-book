"""8 档 bash 工具描述变体草稿。

设计原则（见 README 的 Experiment Design 部分）：
  1. 所有档共享同一套结构骨架：Summary + VALID USES + NEVER LIST + EXAMPLES + ARGS
  2. 短档压缩每部分到 1 行；长档展开加例子、加解释
  3. 差异是详略程度，结构本身不变（让"长度"和"结构"正交）
  4. 每档目标 tokens：{15, 40, 80, 150, 280, 450, 720, 1100}（cl100k_base）
  5. 实测 tokens 用 tiktoken；若实测偏离目标超 ±5%，迭代调整

运行本文件：python _variants_draft.py
    输出每档的 target / actual / delta，供人审核。
"""
from __future__ import annotations

import tiktoken

_enc = tiktoken.get_encoding('cl100k_base')


def toks(s: str) -> int:
    return len(_enc.encode(s))


# ============================================================
# T1 — 目标 15 tokens：几乎无约束（对照组基线）
# ============================================================
T1 = "Execute a shell command. Use only when no dedicated tool fits the task."


# ============================================================
# T2 — 目标 40 tokens：压缩版结构，每段一句
# ============================================================
T2 = (
    "Execute a shell command. Use only when no dedicated tool fits the task. "
    "Valid uses: tests, git, pip/npm, build commands. "
    "Never: cat/ls/grep/sed - translate to the dedicated tool instead."
)


# ============================================================
# T3 — 目标 80 tokens：完整结构骨架，每段列 3-4 项
# ============================================================
T3 = (
    "Execute a shell command. Use only for tasks without a dedicated tool.\n"
    "VALID: running tests (pytest, jest), git operations, package managers, build commands.\n"
    "NEVER use bash for: cat/head/tail (-> read_file), ls/find (-> glob_search), "
    "grep/rg (-> grep_search), sed/awk (-> edit_file).\n"
    "Args: command (required), timeout (optional)."
)


# ============================================================
# T4 — 目标 150 tokens：分段展开，NEVER 列表完整
# ============================================================
T4 = (
    "Execute a shell command. Use ONLY for tasks that have no dedicated tool.\n"
    "\n"
    "VALID USE CASES:\n"
    "  - Running tests: pytest, jest, go test\n"
    "  - Git operations: git status, git log, git diff\n"
    "  - Package management: pip install, npm install\n"
    "  - Starting services: python main.py, npm run dev\n"
    "\n"
    "NEVER use bash for these - use the dedicated tool instead:\n"
    "  - cat, head, tail -> read_file\n"
    "  - ls, find, dir -> glob_search\n"
    "  - grep, rg -> grep_search\n"
    "  - sed, awk, echo > file -> edit_file or write_file\n"
    "\n"
    "Args: command (string, required), timeout (seconds, default 120)."
)


# ============================================================
# T5 — 目标 280 tokens：T4 + 翻译规则 + 每个 NEVER 项的具体示例
# ============================================================
T5 = (
    "Execute a shell command. Use ONLY for tasks that have no dedicated tool.\n"
    "\n"
    "VALID USE CASES (each with a canonical example):\n"
    "  - Running tests: pytest tests/, jest --coverage, go test ./..., cargo test\n"
    "  - Git operations: git status, git log --oneline -5, git diff, git branch\n"
    "  - Package management: pip install requests, npm install axios, cargo add\n"
    "  - Starting services: python main.py, npm run dev, uvicorn app:app\n"
    "  - Build commands: make test, mvn compile, gradle build, cargo build\n"
    "  - Environment probes: which python, node --version\n"
    "\n"
    "NEVER use bash for these - use the dedicated tool instead:\n"
    "  - cat, head, tail, less, more, type -> read_file(path=...)\n"
    "  - ls, find, dir, tree, get-childitem -> glob_search(pattern=...)\n"
    "  - grep, rg, ack, ag, select-string -> grep_search(pattern=..., path=...)\n"
    "  - sed, awk, echo > file, perl -i -> edit_file or write_file\n"
    "\n"
    "TRANSLATION RULE: When the user literally types a forbidden command "
    "(e.g. 'cat README.md', 'ls *.py', 'grep TODO'), do NOT execute it as bash; "
    "translate it to the dedicated tool call with the same intent. "
    "This applies even when the user uses shell syntax explicitly.\n"
    "\n"
    "Args: command (string, required), timeout (seconds integer, default 120)."
)


# ============================================================
# T6 — 目标 450 tokens：T5 + 边界说明 + 每类 valid use 的 1 个具体示例
# ============================================================
T6 = (
    "Execute a shell command. Use ONLY for tasks that have no dedicated tool in "
    "this registry. Dedicated tools are safer (built-in permission checks, path "
    "validation, automatic encoding handling) and faster (no subprocess overhead), "
    "so prefer them whenever they can accomplish the same goal. This is not a "
    "style preference but an operational rule: bash is harder to audit, sandbox, "
    "and reverse than a structured tool call with typed arguments.\n"
    "\n"
    "VALID USE CASES (each with a canonical example):\n"
    "  - Running tests: bash(\"pytest tests/ -v\"), bash(\"jest --coverage\"), bash(\"go test ./...\")\n"
    "  - Git operations: bash(\"git status\"), bash(\"git log --oneline -5\"), bash(\"git diff HEAD~1\")\n"
    "  - Package management: bash(\"pip install requests\"), bash(\"npm install axios\")\n"
    "  - Starting services: bash(\"python main.py\"), bash(\"npm run dev\"), bash(\"uvicorn app:app\")\n"
    "  - Build commands: bash(\"make test\"), bash(\"mvn compile\"), bash(\"gradle build\")\n"
    "  - Environment inspection: bash(\"which python\"), bash(\"python --version\")\n"
    "\n"
    "NEVER use bash for these - use the dedicated tool instead, because the "
    "dedicated tool provides permission checks, consistent encoding across "
    "Windows and Unix, and structured output the agent can parse:\n"
    "  - File reading: cat, head, tail, less, more, type -> read_file(path=...)\n"
    "  - File discovery: ls, find, dir, tree, get-childitem -> glob_search(pattern=...)\n"
    "  - Content search: grep, rg, ack, ag, select-string -> grep_search(pattern=..., path=...)\n"
    "  - File editing: sed, awk, echo > file, perl -i -> edit_file or write_file\n"
    "\n"
    "TRANSLATION RULE: When the user literally types a forbidden command, "
    "do not execute it as bash; translate to the dedicated tool with the same intent. "
    "For example 'cat README.md' -> read_file(path='README.md'); 'ls *.py' -> "
    "glob_search(pattern='**/*.py'); 'grep TODO src/' -> grep_search(pattern='TODO', path='src/'). "
    "This rule applies even when the user insists on the shell form.\n"
    "\n"
    "EDGE CASES: Long-running commands should set timeout explicitly to avoid "
    "hanging; output over 10K chars is truncated (pipe to head/tail if needed); "
    "on Windows use forward slashes in paths and watch for GBK-to-UTF-8 encoding; "
    "avoid interactive commands because they hang until timeout.\n"
    "\n"
    "Args: command (string, required), timeout (seconds integer, default 120)."
)


# ============================================================
# T7 — 目标 720 tokens：T6 + 更多示例 + "为什么用专用工具" 解释
# ============================================================
T7 = (
    "Execute a shell command. Use ONLY for tasks that have no dedicated tool in "
    "this registry. Dedicated tools are safer (built-in permission checks, path "
    "validation, automatic encoding handling, structured output) and faster "
    "(no subprocess overhead, no shell parsing), so prefer them whenever they "
    "can accomplish the same goal. This preference is operational rather than "
    "stylistic: bash commands are harder to audit, harder to sandbox, and harder "
    "to reverse than structured tool calls with typed arguments.\n"
    "\n"
    "VALID USE CASES (each with a canonical example and short explanation):\n"
    "  - Running tests: bash(\"pytest tests/ -v\") or bash(\"jest --coverage\") or "
    "bash(\"go test ./...\"). Test runners have well-defined exit codes and "
    "machine-parseable output, and rarely have side effects outside test dirs.\n"
    "  - Git operations: bash(\"git status\") or bash(\"git log --oneline -5\") or "
    "bash(\"git diff HEAD~1\"). Read-only subcommands are idempotent; for write "
    "operations verify state first with status and diff.\n"
    "  - Package management: bash(\"pip install requests\") or bash(\"npm install axios\"). "
    "Installs modify the environment but are reversible via uninstall; always "
    "verify you are in the correct virtualenv before installing.\n"
    "  - Starting services: bash(\"python main.py\") or bash(\"npm run dev\") or "
    "bash(\"uvicorn app:app --reload\"). Long-running services should set timeout "
    "or run in background; for production use dedicated process managers.\n"
    "  - Build commands: bash(\"make test\") or bash(\"mvn compile\") or "
    "bash(\"cargo build --release\"). Build outputs should be captured and parsed "
    "for error diagnosis; treat build failures as diagnostic signals.\n"
    "\n"
    "NEVER use bash for these - use the dedicated tool instead, since the "
    "dedicated tool provides permission checks, consistent encoding, and "
    "structured output that agents can parse directly:\n"
    "  - File reading: cat, head, tail, less, more, type -> read_file(path=...). "
    "read_file handles UTF-8 automatically, supports offset and limit for large "
    "files, and returns content as a string rather than raw stdout bytes.\n"
    "  - File discovery: ls, find, dir, tree, get-childitem -> glob_search(pattern=...). "
    "glob_search uses portable glob patterns (for example **/*.py) instead of "
    "shell-specific syntax, and works identically on Windows and Unix.\n"
    "  - Content search: grep, rg, ack, ag, select-string -> grep_search(pattern=..., path=...). "
    "grep_search returns file:line:content matches that agents can parse directly "
    "without additional shell pipelines.\n"
    "  - File editing: sed, awk, echo > file, perl -i -> edit_file or write_file. "
    "edit_file does atomic string replacement with backup; both are safer than "
    "in-place shell editing because of atomic write semantics.\n"
    "\n"
    "TRANSLATION RULE: When the user literally types a forbidden command, do not "
    "execute it as bash; translate to the dedicated tool with the same intent. "
    "For example 'cat README.md' should become read_file(path='README.md'); "
    "'ls *.py' should become glob_search(pattern='**/*.py'); 'grep TODO src/' "
    "should become grep_search(pattern='TODO', path='src/'). This is a hard rule.\n"
    "\n"
    "EDGE CASES AND COMMON PITFALLS:\n"
    "  - Long-running commands should set timeout explicitly to avoid hanging.\n"
    "  - Output over 10K chars is truncated; pipe to head or tail to limit size.\n"
    "  - On Windows, use forward slashes in paths and watch for GBK-to-UTF-8 issues.\n"
    "  - Avoid commands that require interactive input; they hang until timeout.\n"
    "  - Shell metacharacters are interpreted by the shell; quote as needed.\n"
    "\n"
    "Args: command (string, required), timeout (seconds integer, default 120)."
)


# ============================================================
# T8 — 目标 1100 tokens：T7 + 冗余解释段（触顶观察注意力稀释）
# ============================================================
T8 = T7 + (
    "\n\n"
    "ADDITIONAL GUIDANCE AND CONTEXT:\n"
    "\n"
    "The preference for dedicated tools over bash is rooted in the operational "
    "invariants that the harness framework relies on. Every dedicated tool has a "
    "typed schema that the model sees, which means the model knows exactly what "
    "arguments are valid before attempting a call. Bash, by contrast, accepts an "
    "arbitrary string and defers all validation to the shell and underlying "
    "programs. This difference matters in three ways. First, typed schemas let "
    "the harness reject malformed calls cheaply at the tool-dispatch layer; "
    "malformed bash commands are only rejected after the shell has already "
    "parsed them, which costs both time and token budget. Second, typed schemas "
    "enable the permission layer to apply granular rules (read-only path sets, "
    "write whitelists, command denylists); bash permission can only work at the "
    "whole-command granularity, which forces the permission system into a binary "
    "allow-or-deny choice rather than a nuanced one. Third, typed schemas make "
    "the audit log useful for post-mortem analysis; an audit log full of arbitrary "
    "bash strings is much harder to reason about than one full of structured "
    "read_file / edit_file / grep_search entries.\n"
    "\n"
    "If you find yourself reaching for bash to read a file, stop and use "
    "read_file instead. If you find yourself reaching for bash to find files, "
    "stop and use glob_search. If you find yourself reaching for bash to search "
    "content, stop and use grep_search. If you find yourself reaching for bash "
    "to modify a file, stop and use edit_file or write_file. The only legitimate "
    "uses of bash are running tests, executing git commands, managing packages, "
    "starting services, and running build commands. Everything else should route "
    "through a dedicated tool.\n"
    "\n"
    "When bash is genuinely required, structure the command defensively: set an "
    "appropriate timeout, avoid interactive flags, capture both stdout and stderr, "
    "and prefer absolute paths over relative ones for clarity. If the command "
    "chain becomes complex (more than two pipes or a conditional), consider "
    "writing a small script with write_file and then invoking it with bash; "
    "this makes the logic readable in the audit log."
)


VARIANTS = {
    15: T1, 40: T2, 80: T3, 150: T4, 280: T5, 450: T6, 720: T7, 1100: T8,
}


if __name__ == '__main__':
    print(f'{"target":>6}  {"actual":>6}  {"chars":>6}  {"delta":>6}  status')
    print('-' * 50)
    for target, text in sorted(VARIANTS.items()):
        actual = toks(text)
        chars = len(text)
        delta_pct = (actual - target) / target * 100
        status = 'OK' if abs(delta_pct) <= 5 else 'TUNE'
        print(f'{target:>6}  {actual:>6}  {chars:>6}  {delta_pct:>+5.1f}%  {status}')
