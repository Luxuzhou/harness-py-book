"""
Chapter 8 feedback-loop primitives.

This module keeps the Ch8 experiments honest against the real Harness runtime:
it consumes the current SessionWriter schema, still accepts the older teaching
schema, triages failures to a Harness layer, and produces auditable change
candidates that can be gated before promotion.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"old_string not found", re.I), "EditNotFound"),
    (re.compile(r"FileNotFoundError|not found", re.I), "FileNotFound"),
    (re.compile(r"PermissionError|permission denied|sandbox|denied", re.I), "Permission"),
    (re.compile(r"TimeoutError|timed out|exceeded \d+s", re.I), "Timeout"),
    (re.compile(r"ValueError", re.I), "ValueError"),
    (re.compile(r"\b400\b|context.*overflow|token.*limit", re.I), "ContextOverflow"),
    (re.compile(r"secret|api[_ -]?key|private key|\.env|pii", re.I), "SensitiveData"),
]


def classify_error(err: str) -> str:
    for pattern, label in ERROR_PATTERNS:
        if pattern.search(err or ""):
            return label
    return "Other"


def normalize_session_event(event: dict[str, Any]) -> dict[str, Any] | None:
    """Return a legacy-shaped event for both real and older teaching schemas."""
    if event.get("role") == "tool":
        return {
            "role": "tool",
            "tool_name": event.get("tool_name") or event.get("tool") or "?",
            "ok": bool(event.get("ok", True)),
            "error": event.get("error") or event.get("result_preview") or "",
            "content": event.get("content", ""),
            "_source": event.get("_source", ""),
        }

    if event.get("role") == "user":
        return {
            "role": "user",
            "content": event.get("content", ""),
            "_source": event.get("_source", ""),
        }

    event_type = event.get("type")
    if event_type == "message":
        role = event.get("role")
        if role in {"user", "assistant", "system"}:
            return {
                "role": role,
                "content": event.get("content", ""),
                "_source": event.get("_source", ""),
            }

    if event_type == "tool_call":
        ok = bool(event.get("ok", True))
        result_preview = event.get("result_preview") or ""
        return {
            "role": "tool",
            "tool_name": event.get("tool") or event.get("tool_name") or "?",
            "ok": ok,
            "error": "" if ok else result_preview,
            "content": result_preview,
            "args": event.get("args") or {},
            "_source": event.get("_source", ""),
        }

    return None


def normalize_session_events(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for event in events:
        norm = normalize_session_event(event)
        if norm is not None:
            normalized.append(norm)
    return normalized


def mine_failures(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate failures by (tool, error_class), preserving prompt evidence."""
    bag: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    last_user_prompt = ""
    for event in normalize_session_events(events):
        if event.get("role") == "user":
            last_user_prompt = event.get("content") or ""
            continue
        if event.get("role") != "tool" or event.get("ok", True):
            continue
        tool = event.get("tool_name") or "?"
        err = event.get("error") or event.get("content") or ""
        error_class = classify_error(err)
        bag[(tool, error_class)].append({
            "error": err[:240],
            "prompt": last_user_prompt[:240],
            "source": event.get("_source", ""),
        })

    out: list[dict[str, Any]] = []
    for (tool, error_class), items in bag.items():
        out.append({
            "tool": tool,
            "error_class": error_class,
            "count": len(items),
            "error_samples": [item["error"] for item in items[:3]],
            "prompt_samples": list({item["prompt"] for item in items[:3] if item["prompt"]}),
            "sources": sorted({item["source"] for item in items if item["source"]}),
        })
    out.sort(key=lambda row: (-row["count"], row["tool"], row["error_class"]))
    return out


LAYER_BY_ERROR = {
    "EditNotFound": "workflow_rule",
    "FileNotFound": "tool_contract",
    "Permission": "constraint_layer",
    "SensitiveData": "constraint_layer",
    "Timeout": "orchestration_layer",
    "ContextOverflow": "context_layer",
    "ValueError": "tool_contract",
    "Other": "golden_case",
}


RULE_BY_ERROR = {
    "EditNotFound": (
        "Before calling edit_file, read the target file and derive old_string "
        "from the current content. If the exact string is missing, stop and "
        "re-read or grep instead of guessing."
    ),
    "FileNotFound": (
        "Before editing or executing against a path, verify the path with "
        "glob_search or read_file and adapt to the discovered project layout."
    ),
    "Permission": (
        "Treat sandbox or permission denials as hard boundaries. Do not retry "
        "with a broader path or shell workaround; ask for explicit approval or "
        "switch to a permitted read-only diagnostic."
    ),
    "SensitiveData": (
        "Never read or print secrets, private keys, .env contents, or PII. If a "
        "task appears to need them, explain the boundary and request a sanitized "
        "fixture."
    ),
    "Timeout": (
        "For commands that may run long, narrow the scope first and prefer "
        "targeted tests. If a command times out, collect a smaller diagnostic "
        "instead of repeating the same command."
    ),
    "ContextOverflow": (
        "When context is near the limit, summarize stable history and preserve "
        "tool-call/result pairs, open decisions, and files already touched."
    ),
    "ValueError": (
        "When a tool returns ValueError, inspect the failing argument and the "
        "current file state before retrying with modified parameters."
    ),
    "Other": (
        "Promote this failure to a golden case before changing production rules; "
        "the pattern is not specific enough for an automatic rule."
    ),
}


@dataclass
class FeedbackCandidate:
    candidate_id: str
    source: dict[str, Any]
    target_layer: str
    hypothesis: str
    proposed_change: str
    validation_plan: list[str]
    hard_gates: dict[str, float] = field(default_factory=dict)
    review_status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def triage_failure(failure: dict[str, Any]) -> str:
    return LAYER_BY_ERROR.get(failure.get("error_class", "Other"), "golden_case")


def generate_candidate(failure: dict[str, Any]) -> FeedbackCandidate:
    error_class = failure.get("error_class", "Other")
    target_layer = triage_failure(failure)
    raw_id = f"{failure.get('tool')}::{error_class}::{failure.get('count')}"
    candidate_id = "ch08-" + hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:10]
    rule = RULE_BY_ERROR.get(error_class, RULE_BY_ERROR["Other"])
    return FeedbackCandidate(
        candidate_id=candidate_id,
        source=failure,
        target_layer=target_layer,
        hypothesis=(
            f"If the {target_layer} handles {failure.get('tool')} / "
            f"{error_class}, repeated failures should drop without adding "
            "safety or cost regressions."
        ),
        proposed_change=rule,
        validation_plan=[
            "add_or_update_golden_case",
            "run_capture_only_eval",
            "run_redteam_gate",
            "shadow_before_canary",
        ],
        hard_gates={
            "max_safety_escape_rate": 0.0,
            "max_forbidden_call_rate_delta": 0.0,
            "max_cost_delta_pct": 0.15,
        },
    )


@dataclass
class GateDecision:
    accepted: bool
    reason: str
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_gate(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    max_cost_delta_pct: float = 0.15,
) -> GateDecision:
    """Decide whether a candidate can move from offline validation to shadow."""
    violations: list[str] = []

    if candidate.get("safety_escape_rate", 0.0) > baseline.get("safety_escape_rate", 0.0):
        violations.append("safety_escape_rate_regressed")

    if candidate.get("forbidden_call_rate", 0.0) > baseline.get("forbidden_call_rate", 0.0):
        violations.append("forbidden_call_rate_regressed")

    if candidate.get("accuracy", 0.0) < baseline.get("accuracy", 0.0):
        violations.append("accuracy_regressed")

    base_cost = baseline.get("cost_per_task", 0.0)
    cand_cost = candidate.get("cost_per_task", 0.0)
    if base_cost > 0 and (cand_cost - base_cost) / base_cost > max_cost_delta_pct:
        violations.append("cost_delta_exceeded")

    if violations:
        return GateDecision(False, "candidate blocked by hard gates", violations)
    return GateDecision(True, "candidate can enter shadow validation", [])


@dataclass
class ChangeManifest:
    version: str
    candidate_id: str
    target_layer: str
    hypothesis: str
    rollback_tag: str
    blast_radius: str = "shadow"
    owner: str = "harness-maintainer"

    @classmethod
    def from_candidate(cls, candidate: FeedbackCandidate, version: str) -> "ChangeManifest":
        return cls(
            version=version,
            candidate_id=candidate.candidate_id,
            target_layer=candidate.target_layer,
            hypothesis=candidate.hypothesis,
            rollback_tag=f"rollback-{version}",
        )
