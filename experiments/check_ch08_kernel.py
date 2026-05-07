"""
No-LLM kernel checks for Chapter 8 feedback-loop experiments.

The goal is not to prove model quality. It proves that the feedback controller
has stable engineering interfaces: telemetry normalization, failure mining,
candidate generation, hard gates, prompt injection through AgentConfig, and a
rollback manifest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CH08_DIR = REPO_ROOT / "experiments" / "ch08"
EXP1_DIR = CH08_DIR / "exp1_eval_framework_extended"
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(CH08_DIR))
sys.path.insert(0, str(EXP1_DIR))

from feedback_loop import (  # noqa: E402
    ChangeManifest,
    evaluate_gate,
    generate_candidate,
    mine_failures,
    normalize_session_event,
)
from harness_py_pro.config import AgentConfig  # noqa: E402
from harness_py_pro.session import SessionWriter  # noqa: E402
from subjects.system_prompt import SystemPromptSubject  # noqa: E402


def _check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"{name} failed: {detail}")
    print(f"[ok] {name}")


def test_session_writer_schema() -> None:
    root = CH08_DIR / "_kernel_runtime"
    root.mkdir(exist_ok=True)
    path = root / "ch08test.jsonl"
    path.unlink(missing_ok=True)
    writer = SessionWriter("ch08test", root, root)
    writer.write_tool_call(
        "edit_file",
        {"path": "src/app.py"},
        False,
        "ValueError: old_string not found in file",
    )
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    path.unlink(missing_ok=True)
    try:
        root.rmdir()
    except OSError:
        pass
    tool_event = next(e for e in events if e.get("type") == "tool_call")
    _check("session_writer_role", tool_event.get("role") == "tool")
    _check("session_writer_tool_name", tool_event.get("tool_name") == "edit_file")
    _check("session_writer_error", "old_string not found" in tool_event.get("error", ""))


def test_failure_mining_normalizes_real_and_legacy_events() -> list[dict]:
    events = [
        {"type": "message", "role": "user", "content": "fix parser indent"},
        {
            "type": "tool_call",
            "tool": "edit_file",
            "args": {"path": "src/parser.py"},
            "ok": False,
            "result_preview": "ValueError: old_string not found in file",
        },
        {"role": "user", "content": "run tests"},
        {"role": "tool", "tool_name": "bash", "ok": False, "error": "TimeoutError: exceeded 30s"},
    ]
    normalized = [normalize_session_event(e) for e in events]
    _check("normalize_real_tool_call", normalized[1]["tool_name"] == "edit_file")
    failures = mine_failures(events)
    keys = {(row["tool"], row["error_class"]) for row in failures}
    _check("mine_real_schema", ("edit_file", "EditNotFound") in keys)
    _check("mine_legacy_schema", ("bash", "Timeout") in keys)
    return failures


def test_candidate_and_gate(failures: list[dict]) -> None:
    failure = next(row for row in failures if row["error_class"] == "EditNotFound")
    candidate = generate_candidate(failure)
    _check("candidate_target_layer", candidate.target_layer == "workflow_rule")
    _check("candidate_validation_plan", "run_redteam_gate" in candidate.validation_plan)
    _check("candidate_rule_specific", "read" in candidate.proposed_change.lower())

    baseline = {
        "accuracy": 0.80,
        "cost_per_task": 0.10,
        "forbidden_call_rate": 0.02,
        "safety_escape_rate": 0.0,
    }
    accepted = evaluate_gate(
        baseline,
        {
            "accuracy": 0.84,
            "cost_per_task": 0.108,
            "forbidden_call_rate": 0.02,
            "safety_escape_rate": 0.0,
        },
    )
    rejected = evaluate_gate(
        baseline,
        {
            "accuracy": 0.86,
            "cost_per_task": 0.10,
            "forbidden_call_rate": 0.02,
            "safety_escape_rate": 0.01,
        },
    )
    _check("gate_accepts_safe_improvement", accepted.accepted)
    _check("gate_rejects_safety_regression", not rejected.accepted)

    manifest = ChangeManifest.from_candidate(candidate, "ch08.2026-04-30")
    _check("manifest_rollback_tag", manifest.rollback_tag == "rollback-ch08.2026-04-30")


def test_prompt_subject_uses_agent_config() -> None:
    subject = SystemPromptSubject(name="system_prompt", version="v2")
    config = subject.configure_agent(AgentConfig())
    _check("prompt_subject_role_prompt", "read_file" in config.role_prompt)
    _check("prompt_subject_no_monkey_patch_state", subject._saved_state is None)


def main() -> int:
    test_session_writer_schema()
    failures = test_failure_mining_normalizes_real_and_legacy_events()
    test_candidate_and_gate(failures)
    test_prompt_subject_uses_agent_config()
    print("\nCh8 feedback-loop kernel checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
