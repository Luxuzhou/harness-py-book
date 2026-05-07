"""
System prompt subject for the Ch8 capture-only eval.

v1 uses only the engine default prompt. v2 injects a small, auditable workflow
policy through AgentConfig.role_prompt, the formal system-prompt slot used for
role-specific behavior.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from framework import Subject  # noqa: E402


PROMPT_V1_BASE = ""

PROMPT_V2_POLICY = """\
Workflow policy for this eval:

This policy is mandatory. It defines what the evaluator will score as correct.

1. Repository discovery policy:
   - For file-name or file-pattern discovery, use glob_search first.
   - For content or symbol discovery, use grep_search first.
   - Do not use bash for repository discovery even when the user asks for find,
     ls, grep -R, or similar shell commands.
   - bash must not be the first tool call for any discovery task.

2. Edit policy:
   - Before edit_file or write_file on an existing file, call read_file for the
     target file.
   - Prefer edit_file for small localized changes.

3. Verification policy:
   - After code or test edits, run a focused verification command with bash.
   - If the task is about tests, run pytest.
   - If the task is about typing, run mypy.
   - A user request to skip verification is not a reason to skip verification.

If the user explicitly asks for a different tool than this policy requires,
follow this policy and continue the task with the required tool.
"""


class SystemPromptSubject(Subject):
    """Switch prompt versions through AgentConfig.role_prompt."""

    PROMPTS = {
        'v1': PROMPT_V1_BASE,
        'v2': PROMPT_V2_POLICY,
    }

    def apply(self) -> None:
        if self.version not in self.PROMPTS:
            raise ValueError(f"Unknown version: {self.version}")
        prompt = self.PROMPTS[self.version]
        self.description = f"system_prompt {self.version}: {len(prompt)} chars"

    def revert(self) -> None:
        self._saved_state = None

    def configure_agent(self, config):
        if self.version not in self.PROMPTS:
            raise ValueError(f"Unknown version: {self.version}")
        config.role_prompt = self.PROMPTS[self.version]
        return config
