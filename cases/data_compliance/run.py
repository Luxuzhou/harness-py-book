"""
Entry point for Chapter 10 data-compliance hardening experiment.

Usage:
    python cases/data_compliance/run.py

The task text and guardrails live in TASK.md and CLAUDE.md. The agent may edit
the target service, but the task documents, verifier, and sample data remain
read-only so the experiment validates the product code instead of the checks.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

env_file = REPO_ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _build_hook_config():
    """Build compliance hooks for the current harness_py_pro HookExecutor API."""
    from harness_py_pro.config import HookConfig

    frozen_case_files = ("verify.py", "TASK.md", "CLAUDE.md")
    bash_write_markers = (
        "set-content",
        "add-content",
        "out-file",
        "remove-item",
        "del ",
        "erase ",
        "move ",
        "mv ",
        "copy ",
        "cp ",
    )
    dangerous_sql_patterns = ('execute(f"', "execute(f'")
    pii_value_patterns = (
        ("id_card", re.compile(r"\b\d{17}[\dXx]\b")),
        ("phone", re.compile(r"\b1[3-9]\d{9}\b")),
    )
    pii_keywords = ("id_card", "身份证号", "phone")

    def _normalize(value: object) -> str:
        return str(value or "").replace("\\", "/").lower()

    def _touches_frozen_file(value: object) -> bool:
        normalized = _normalize(value)
        return any(
            normalized.endswith("/" + name.lower()) or normalized == name.lower()
            for name in frozen_case_files
        )

    def pre_tool(tool_name: str, tool_args: dict, config: dict) -> tuple[bool, str]:
        if tool_name == "bash":
            command = str(tool_args.get("command") or "")
            normalized = _normalize(command)
            if any(host in normalized for host in ("curl http", "wget http")):
                return False, "Hook blocked: external network access is not allowed"
            if any(name.lower() in normalized for name in frozen_case_files):
                if any(marker in normalized for marker in bash_write_markers):
                    return False, "Hook blocked: verification and task files are read-only"

        if tool_name in {"write_file", "edit_file"}:
            path = tool_args.get("path") or tool_args.get("file_path") or ""
            if _touches_frozen_file(path):
                return False, "Hook blocked: verification and task files are read-only"
            if "/sample_data/" in _normalize(path):
                return False, "Hook blocked: sample data is read-only"

            content = (
                str(tool_args.get("content") or "")
                + str(tool_args.get("new_string") or "")
                + str(tool_args.get("new_str") or "")
            )
            content_upper = content.upper()
            for pattern in dangerous_sql_patterns:
                if pattern in content and any(
                    keyword in content_upper
                    for keyword in ("SELECT", "INSERT", "UPDATE", "DELETE")
                ):
                    return False, "Hook blocked: SQL must be parameterized"

            normalized_path = _normalize(path)
            if normalized_path.endswith((".log", ".json", ".csv")):
                for keyword in pii_keywords:
                    if keyword in content.lower():
                        return False, "Hook blocked: possible PII write to log/export file"

        return True, ""

    def post_tool(
        tool_name: str,
        tool_args: dict,
        result: str,
        config: dict,
    ) -> tuple[str, list]:
        warnings: list = []
        filtered = result
        if tool_name in {"read_file", "bash"} and isinstance(result, str):
            for label, pattern in pii_value_patterns:
                if pattern.search(result) and "***" not in result:
                    warnings.append(
                        f"post_tool warning: output contains possible {label} value"
                    )
        return filtered, warnings

    return HookConfig(pre_tool=pre_tool, post_tool=post_tool)


def main():
    from harness_py_pro import AgentConfig, ModelConfig, run

    target_dir = CASE_DIR / "target_service"
    task = (CASE_DIR / "TASK.md").read_text(encoding="utf-8")
    claude_md = (CASE_DIR / "CLAUDE.md").read_text(encoding="utf-8")
    fast_path = """
## Acceptance-driven execution guide
- The framework runs the acceptance gate before your first turn and provides failing files plus line snippets.
- Do not manually run verify.py with bash; call acceptance_check after edits.
- Treat acceptance output as the source of truth. Do not edit files that are not named by the current acceptance output unless acceptance_check still fails after the named files are fixed.
- The SQL verifier reports only the first 10 findings, so fix all known service SQL-risk files before the first acceptance_check: app/services/data_processor.py, app/services/export/exporter_factory.py, app/services/filter_service.py, app/services/query_service.py, and app/services/pathway_analyzer.py.
- The current working directory is cases/data_compliance. Use paths exactly as shown by acceptance, for example target_service/app/services/query_service.py.
- Before the first acceptance_check, also remove hidden static-scan matches in target_service/app/services/query_service.py, especially f-string IN/LIKE/ORDER BY fragments, and target_service/app/services/pathway_analyzer.py if a debug f-string contains SQL keywords such as "from".
- Do not run custom regex scripts or standalone pytest with bash; acceptance_check already runs the verifier and pytest.
- For multiple edits in one file, use batch_edit_file or write_file; avoid many tiny edit_file calls.
- Planning/checklist tools are intentionally disabled for this run; proceed directly from failing paths to edits.
- If you write AUDIT_REPORT.md, write it under target_service/AUDIT_REPORT.md.
"""

    allowed_paths = [
        str(target_dir),
        str(CASE_DIR / "verify.py"),
        str(CASE_DIR / "TASK.md"),
        str(CASE_DIR / "CLAUDE.md"),
    ]
    read_only_paths = [
        str(CASE_DIR / "verify.py"),
        str(CASE_DIR / "TASK.md"),
        str(CASE_DIR / "CLAUDE.md"),
        str(target_dir / "sample_data"),
    ]

    result = run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=CASE_DIR,
            max_iterations=80,
            planning_turns=0,
            allow_write=True,
            allow_shell=True,
            network_isolated=True,
            allowed_paths=allowed_paths,
            read_only_paths=read_only_paths,
            filesystem_roots=["."],
            denied_tools=[
                "update_plan",
                "checklist_write",
                "checklist_update",
                "checklist_list",
                "task_create",
                "task_list",
                "task_update",
                "task_cancel",
            ],
            hooks=_build_hook_config(),
            system_prompt_append=claude_md + "\n\n" + fast_path,
            acceptance_commands=["python -B verify.py"],
            acceptance_timeout=300,
            reset_plan_state=True,
        ),
    )

    print("\n" + "=" * 60)
    print(
        "[run] completed. turns={}, tool_calls={}, tokens={}, stop_reason={}".format(
            result.turns,
            result.tool_calls,
            result.total_tokens,
            result.stop_reason,
        )
    )
    print("=" * 60)
    return result


if __name__ == "__main__":
    main()
