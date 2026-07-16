"""
Chapter 12 full-case evaluation runner.

This script intentionally imports each case's own run.py and verify.py. Chapter
12 should measure the behavior of the chapter cases themselves, not a duplicate
wrapper configuration that can drift from the book code.

Usage:
    python experiments/ch12/run_all_cases.py
    python experiments/ch12/run_all_cases.py --baseline experiments/ch12/baseline.json
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

RESULTS_DIR = ROOT / 'experiments' / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _load_env() -> None:
    env_file = ROOT / '.env'
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())


def _load_main(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'cannot load module: {path}')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod.main


class TeeWriter:
    def __init__(self, original, buffer):
        self.original = original
        self.buffer = buffer

    def write(self, s):
        self.original.write(s)
        self.buffer.write(s)

    def flush(self):
        self.original.flush()
        self.buffer.flush()


def _serialize_result(result) -> dict | str | None:
    if result is None:
        return None
    if hasattr(result, '__dict__'):
        data = {}
        for k, v in result.__dict__.items():
            try:
                json.dumps(v)
                data[k] = v
            except (TypeError, ValueError):
                data[k] = str(v)
        return data
    return str(result)


def capture_run(name: str, run_fn, verify_fn=None) -> dict:
    print(f'\n{"#" * 60}')
    print(f'# {name}')
    print(f'# {datetime.now().isoformat()}')
    print(f'{"#" * 60}\n')

    record = {
        'name': name,
        'start_time': datetime.now().isoformat(),
        'run_output': '',
        'run_error': '',
        'verify_output': '',
        'verify_error': '',
        'run_result': None,
        'verify_passed': None,
        'duration_seconds': 0,
        'exception': None,
    }

    t0 = time.time()
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    old_stdout, old_stderr = sys.stdout, sys.stderr

    try:
        sys.stdout = TeeWriter(old_stdout, stdout_buf)
        sys.stderr = TeeWriter(old_stderr, stderr_buf)
        result = run_fn()
        record['run_result'] = _serialize_result(result)
    except Exception as exc:
        record['exception'] = f'{type(exc).__name__}: {exc}\n{traceback.format_exc()}'
        print(f'[ERROR] {name} run failed: {exc}')
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    record['run_output'] = stdout_buf.getvalue()
    record['run_error'] = stderr_buf.getvalue()
    record['duration_seconds'] = round(time.time() - t0, 1)
    record['end_time'] = datetime.now().isoformat()

    if verify_fn:
        v_stdout = io.StringIO()
        v_stderr = io.StringIO()
        try:
            sys.stdout = TeeWriter(old_stdout, v_stdout)
            sys.stderr = TeeWriter(old_stderr, v_stderr)
            record['verify_passed'] = bool(verify_fn())
        except Exception as exc:
            record['verify_error'] = f'{type(exc).__name__}: {exc}\n{traceback.format_exc()}'
            print(f'[ERROR] {name} verify failed: {exc}')
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        record['verify_output'] = v_stdout.getvalue()
        record['verify_error'] += v_stderr.getvalue()

    safe_name = name.replace(' ', '_').replace(':', '')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = RESULTS_DIR / f'{safe_name}_{ts}.json'
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f'\n[SAVED] {out_path}')

    log_path = RESULTS_DIR / f'{safe_name}_{ts}.log'
    log_path.write_text(
        '\n'.join([
            f'=== {name} ===',
            f'time: {record["start_time"]} - {record.get("end_time", "")}',
            f'duration: {record["duration_seconds"]}s',
            '',
            '--- run output ---',
            record['run_output'],
            '',
            '--- run error ---',
            record['run_error'],
            '',
            '--- verify output ---',
            record['verify_output'],
            '',
            '--- verify error ---',
            record['verify_error'],
            '',
            '--- exception ---',
            record['exception'] or '',
        ]),
        encoding='utf-8',
    )
    print(f'[SAVED] {log_path}')
    return record


def run_case1():
    return _load_main(
        'run_refactor',
        ROOT / 'cases' / 'refactor_enterprise' / 'run.py',
    )()


def verify_case1():
    return _load_main(
        'verify_refactor',
        ROOT / 'cases' / 'refactor_enterprise' / 'verify.py',
    )()


def run_case2():
    return _load_main(
        'run_compliance',
        ROOT / 'cases' / 'data_compliance' / 'run.py',
    )()


def verify_case2():
    return _load_main(
        'verify_compliance',
        ROOT / 'cases' / 'data_compliance' / 'verify.py',
    )()


def run_case3():
    return _load_main(
        'run_multiagent',
        ROOT / 'cases' / 'multiagent_enterprise' / 'run.py',
    )()


def verify_case3():
    return _load_main(
        'verify_multiagent',
        ROOT / 'cases' / 'multiagent_enterprise' / 'verify.py',
    )()


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_baseline(path: Path | None) -> dict:
    if path is None:
        return {}
    if not path.exists():
        raise SystemExit(f'baseline file not found: {path}')
    return json.loads(path.read_text(encoding='utf-8'))


def _check_baseline(summary: list[dict], baseline: dict) -> list[str]:
    if not baseline:
        return []
    failures: list[str] = []
    for item in summary:
        base = baseline.get(item['name'], {})
        if not isinstance(base, dict):
            continue
        allowed = _as_float(base.get('cost_usd_110pct', base.get('cost_usd')))
        actual = _as_float(item.get('cost'))
        if allowed is not None and actual is not None:
            limit = allowed if 'cost_usd_110pct' in base else allowed * 1.10
            if actual > limit:
                failures.append(f'{item["name"]}: cost ${actual:.4f} > baseline limit ${limit:.4f}')
    return failures


def main(argv: list[str] | None = None) -> bool:
    parser = argparse.ArgumentParser(description='Run Chapter 12 full-case evaluation.')
    parser.add_argument('--baseline', type=Path, help='Optional JSON cost baseline.')
    args = parser.parse_args(argv)

    _load_env()
    baseline = _load_baseline(args.baseline)

    print('=' * 60)
    print('Harness-py Book - Chapter 12 full-case evaluation')
    print(f'time: {datetime.now().isoformat()}')
    print(f'repo root: {ROOT}')
    print(f'results dir: {RESULTS_DIR}')
    print('=' * 60)

    api_key = os.getenv('HARNESS_API_KEY', os.getenv('OPENAI_API_KEY', ''))
    if not api_key:
        print('[FATAL] missing OPENAI_API_KEY or HARNESS_API_KEY in environment/.env')
        return False
    print(f'API Key: ...{api_key[-8:]}')
    print(f'Model: {os.getenv("HARNESS_MODEL", os.getenv("MODEL", "deepseek-v4-flash"))}')
    print()

    cases = [
        ('Case1_RefactorEnterprise', run_case1, verify_case1),
        ('Case2_DataCompliance', run_case2, verify_case2),
        ('Case3_MultiagentEnterprise', run_case3, verify_case3),
    ]

    summary = []
    for name, run_fn, verify_fn in cases:
        record = capture_run(name, run_fn, verify_fn)
        run_result = record.get('run_result') if isinstance(record.get('run_result'), dict) else {}
        summary.append({
            'name': name,
            'duration': record['duration_seconds'],
            'turns': run_result.get('turns', '?'),
            'tool_calls': run_result.get('tool_calls', '?'),
            'tokens': run_result.get('total_tokens', '?'),
            'cost': run_result.get('cost_usd', '?'),
            'cost_summary': run_result.get('cost_summary', {}),
            'guard_stats': run_result.get('guard_stats', {}),
            'hook_warnings': run_result.get('hook_warnings', []),
            'verify': record.get('verify_passed', '?'),
            'error': record.get('exception', '')[:100] if record.get('exception') else '',
        })
        print()

    print('\n' + '=' * 60)
    print('Experiment summary')
    print('=' * 60)
    for item in summary:
        status = 'PASS' if item['verify'] else ('FAIL' if item['verify'] is False else 'N/A')
        error = f' [{item["error"]}]' if item['error'] else ''
        print(
            f'  {item["name"]}: {item["duration"]}s, {item["turns"]} turns, '
            f'{item["tool_calls"]} tools, {item["tokens"]} tokens, '
            f'${item["cost"]}, verify={status}{error}'
        )

    failures = _check_baseline(summary, baseline)
    if failures:
        print('\n[BASELINE FAIL]')
        for failure in failures:
            print(f'  - {failure}')

    summary_path = RESULTS_DIR / f'summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(f'\n[SAVED] {summary_path}')
    return not failures and all(item.get('verify') is not False for item in summary)


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
