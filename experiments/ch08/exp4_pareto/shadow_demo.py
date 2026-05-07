"""
Shadow Testing minimal demo.

Corresponds to book section 8.6.2. Runs two Subject configurations
on the same task and compares their tool-call sequences.

Modes:
  1. offline (default): compare two pre-recorded session files
  2. live (--live):     actually call the LLM with two Subjects

Usage:
    python shadow_demo.py                           # offline mode
    python shadow_demo.py --live --smoke             # live mode (3 tasks x 1 seed)
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / 'experiments' / 'ch08'))
sys.path.insert(0, str(_REPO_ROOT / 'experiments' / 'ch08' / 'exp1_eval_framework_extended'))

SAMPLE_DIR = _REPO_ROOT / 'experiments' / 'ch08' / 'exp2_failure_mining' / 'sessions_sample'
TASKS_FILE = (_REPO_ROOT / 'experiments' / 'ch08' / 'exp1_eval_framework_extended'
              / 'fixtures' / 'system_prompt_tasks.jsonl')
RESULTS = Path(__file__).parent / 'results'
RESULTS.mkdir(exist_ok=True)


# -- Offline mode: compare two pre-recorded session files --

def load_session_turns(path: Path) -> list[dict]:
    turns: list[dict] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.strip():
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return turns


def format_call(turn: dict) -> str:
    tool = turn.get('tool_name') or turn.get('tool') or '?'
    params = turn.get('params') or turn.get('args') or {}
    param_str = ', '.join(f"{k}={v}" for k, v in list(params.items())[:3])
    ok = 'OK' if turn.get('ok', True) else 'FAIL'
    return f"  {ok} {tool}({param_str})"


def diff_sessions(prod_turns: list[dict], shadow_turns: list[dict],
                  label_prod: str = "prod", label_shadow: str = "shadow") -> str:
    prod_calls = [t for t in prod_turns if t.get('role') == 'tool'
                  or t.get('type') == 'tool_call']
    shadow_calls = [t for t in shadow_turns if t.get('role') == 'tool'
                    or t.get('type') == 'tool_call']

    prod_lines = [format_call(t) for t in prod_calls]
    shadow_lines = [format_call(t) for t in shadow_calls]

    diff = list(difflib.unified_diff(
        prod_lines, shadow_lines,
        fromfile=label_prod, tofile=label_shadow,
        lineterm='',
    ))

    prod_ok = sum(1 for t in prod_calls if t.get('ok', True))
    shadow_ok = sum(1 for t in shadow_calls if t.get('ok', True))
    prod_errs = [t for t in prod_calls if not t.get('ok', True)]
    shadow_errs = [t for t in shadow_calls if not t.get('ok', True)]

    lines = [f"Shadow Test Diff: {label_prod} vs {label_shadow}"]
    lines.append("=" * 60)
    lines.append(f"")
    lines.append(f"  PROD  ({label_prod}): {len(prod_calls)} calls, {prod_ok} ok")
    lines.append(f"  SHADOW({label_shadow}): {len(shadow_calls)} calls, {shadow_ok} ok")
    lines.append(f"")

    if prod_errs:
        lines.append(f"  PROD errors:")
        for t in prod_errs:
            err = t.get('error', '')[:80]
            lines.append(f"    FAIL {t.get('tool_name', '?')}: {err}")
    if shadow_errs:
        lines.append(f"  SHADOW errors:")
        for t in shadow_errs:
            err = t.get('error', '')[:80]
            lines.append(f"    FAIL {t.get('tool_name', '?')}: {err}")

    lines.append(f"")
    if diff:
        lines.append(f"  Call sequence diff ({len(diff)} lines):")
        lines.append(f"")
        lines.extend(diff)
    else:
        lines.append(f"  Call sequences identical -- no diff.")
        lines.append(f"  -> Shadow validation: PASS")

    lines.append(f"")
    lines.append(f"Conclusion: Shadow diff {'EXISTS (review needed)' if diff else 'EMPTY (safe)'}")
    return '\n'.join(lines)


def run_offline():
    sessions = sorted(SAMPLE_DIR.glob('*.jsonl'))
    if len(sessions) < 2:
        print(f"Need >= 2 session files, found {len(sessions)}")
        return 1

    prod_turns = load_session_turns(sessions[0])
    shadow_turns = load_session_turns(sessions[1])
    report = diff_sessions(prod_turns, shadow_turns,
                           label_prod=sessions[0].stem,
                           label_shadow=sessions[1].stem)

    out_path = RESULTS / 'shadow_diff_offline.txt'
    out_path.write_text(report, encoding='utf-8')
    print(f"[shadow_demo] Offline shadow diff written to {out_path}")
    print(f"             Compare: {sessions[0].name} vs {sessions[1].name}")
    return 0


# -- Live mode: actually call the LLM --

def run_live(smoke: bool = False):
    _env_file = _REPO_ROOT / '.env'
    if _env_file.exists():
        for _line in _env_file.read_text(encoding='utf-8').splitlines():
            if '=' in _line and not _line.strip().startswith('#'):
                k, _, v = _line.partition('=')
                os.environ.setdefault(k.strip(), v.strip())
    _resolved_key = (os.environ.get('DEEPSEEK_API_KEY')
                     or os.environ.get('HARNESS_API_KEY')
                     or os.environ.get('OPENAI_API_KEY') or '')
    if _resolved_key:
        os.environ.setdefault('DEEPSEEK_API_KEY', _resolved_key)
    _resolved_base = (os.environ.get('DEEPSEEK_BASE_URL')
                      or os.environ.get('HARNESS_BASE_URL')
                      or os.environ.get('OPENAI_BASE_URL') or '')
    if _resolved_base:
        os.environ.setdefault('DEEPSEEK_BASE_URL', _resolved_base)

    from framework import Task, _build_capture_registry, _EVAL_SANDBOX, prepare_eval_sandbox
    from harness_py_pro import run as engine_run
    from harness_py_pro.config import AgentConfig, ModelConfig

    from subjects.system_prompt import SystemPromptSubject

    tasks = Task.from_jsonl(TASKS_FILE)
    if smoke:
        tasks = tasks[:3]

    prod_subj = SystemPromptSubject(name='system_prompt', version='v1')
    shadow_subj = SystemPromptSubject(name='system_prompt', version='v2')

    mc = ModelConfig(
        model='deepseek-chat',
        api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
        base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
        context_window=64000, temperature=0.0, seed=42,
    )
    base_ac = AgentConfig(
        cwd=_EVAL_SANDBOX, max_iterations=5, planning_turns=0,
        allow_write=True, allow_shell=True, sandbox_mode='bypass', network_isolated=True,
    )

    report_lines = ["=" * 60,
                    "Live Shadow Testing Demo",
                    "=" * 60,
                    "",
                    f"  PROD Subject  : system_prompt v1 (baseline)",
                    f"  SHADOW Subject: system_prompt v2 (workflow policy)",
                    ""]

    for task in tasks:
        report_lines.append(f"-- Task: {task.id} --")
        report_lines.append(f"  Request: {task.user_prompt[:80]}")
        report_lines.append("")

        for state_label, subject in [('PROD', prod_subj), ('SHADOW', shadow_subj)]:
            captured: list[dict] = []
            prepare_eval_sandbox()
            registry = _build_capture_registry(captured)
            ac = subject.configure_agent(base_ac)

            try:
                result = engine_run(
                    task=task.user_prompt, model_config=mc,
                    agent_config=ac, tool_registry=registry, verbose=False,
                )
                err = None
            except Exception as e:
                err = str(e)[:100]

            calls = [c['name'] for c in captured]
            call_str = ', '.join(calls) if calls else '(none)'
            err_str = f" ERROR: {err}" if err else ''
            report_lines.append(f"  [{state_label:6}] first={calls[0] if calls else '?'} calls=({call_str}){err_str}")

        report_lines.append("")

    report_lines.append("=" * 60)
    report_lines.append("Shadow validation complete.")
    report_lines.append("Review tool-call differences before canary.")

    out_path = RESULTS / 'shadow_diff_live.txt'
    report = '\n'.join(report_lines)
    out_path.write_text(report, encoding='utf-8')
    print(f"[shadow_demo] Live shadow comparison written to {out_path}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--live', action='store_true', help='Live mode (calls LLM)')
    ap.add_argument('--smoke', action='store_true', help='Live mode: 3 tasks only')
    args = ap.parse_args()

    if args.live:
        return run_live(smoke=args.smoke)
    return run_offline()


if __name__ == '__main__':
    raise SystemExit(main())
