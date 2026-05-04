"""
Ch9-Ch12 Harness kernel gate.

This offline check does not call an LLM and does not modify case code. It verifies
that the four late-book chapters are backed by visible Harness controls rather
than prompt-only claims.

Run:
    python experiments/check_ch09_ch12_kernel.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def has_all(text: str, tokens: list[str]) -> tuple[bool, str]:
    missing = [token for token in tokens if token not in text]
    return not missing, ', '.join(missing)


def check_ch9() -> list[Check]:
    run_text = read(ROOT / 'cases' / 'refactor_enterprise' / 'run.py')
    verify_text = read(ROOT / 'cases' / 'refactor_enterprise' / 'verify.py')
    ok, missing = has_all(run_text, [
        'planning_turns=5',
        'max_iterations=60',
        "sandbox_mode='bypass'",
        'network_isolated=True',
        'allowed_paths=',
        'hooks=hooks',
        'system_prompt_append=claude_md',
    ])
    checks = [
        Check('Ch9 runtime controls', ok, missing or 'planning/tools/sandbox/hooks/context injection enabled'),
    ]
    ok, missing = has_all(verify_text, [
        'check_api_contracts_unchanged',
        'check_controller_depends_on_split_services',
        'check_tests_exist',
        'check_java_syntax',
        'check_no_unauthorized_changes',
    ])
    checks.append(Check('Ch9 verification gates', ok, missing or 'contract/refactor/tests/compile/scope gates present'))
    return checks


def check_ch10() -> list[Check]:
    run_text = read(ROOT / 'cases' / 'data_compliance' / 'run.py')
    verify_text = read(ROOT / 'cases' / 'data_compliance' / 'verify.py')
    ok, missing = has_all(run_text, [
        'post_fail_closed=True',
        "read_only_paths=['sample_data']",
        "sandbox_mode='bypass'",
        'network_isolated=True',
        'allowed_paths=',
        'system_prompt_append=claude_md',
    ])
    checks = [
        Check('Ch10 compliance controls', ok, missing or 'fail-closed hooks/read-only data/network isolation enabled'),
    ]
    ok, missing = has_all(verify_text, [
        'check_sql_parameterized',
        'check_pii_masking_defined',
        'check_audit_middleware_registered',
        'check_network_policy',
        'check_pytest_passes',
    ])
    checks.append(Check('Ch10 compliance gates', ok, missing or 'SQL/PII/audit/network/tests gates present'))
    return checks


def check_ch11() -> list[Check]:
    run_text = read(ROOT / 'cases' / 'multiagent_enterprise' / 'run.py')
    verify_text = read(ROOT / 'cases' / 'multiagent_enterprise' / 'verify.py')
    ok, missing = has_all(run_text, [
        'round_plan=',
        'parallel_groups=',
        "sandbox_mode='bypass'",
        'network_isolated=True',
        'allowed_paths=',
        'filesystem_roots=',
        'read_only_paths=',
    ])
    checks = [
        Check('Ch11 staged swarm controls', ok, missing or 'round plan/parallel groups/role boundaries enabled'),
    ]
    ok, missing = has_all(verify_text, [
        'check_harness_controls',
        'check_contract_consistency',
        'check_architect_plan',
        'check_test_report',
    ])
    checks.append(Check('Ch11 orchestration gates', ok, missing or 'controls/contracts/artifacts/QA report gates present'))
    return checks


def check_ch12() -> list[Check]:
    from harness_py_pro.token_budget import CostTracker, MODEL_PRICING

    observe_text = read(ROOT / 'examples' / 'ch12_observe.py')
    run_all_text = read(ROOT / 'experiments' / 'ch12' / 'run_all_cases.py')

    ct = CostTracker()
    exact_pricing_ok = (
        ct._find_pricing('gpt-4o-mini') == MODEL_PRICING['gpt-4o-mini']
        and ct._find_pricing('gpt-4.1-nano') == MODEL_PRICING['gpt-4.1-nano']
    )
    ct.record('unknown-model-for-test', 100, 100)
    unknown_ok = 'unknown-model-for-test' in ct.summary().get('unknown_models', [])

    return [
        Check('Ch12 pricing exact match', exact_pricing_ok, 'mini/nano pricing resolved before parent model names'),
        Check('Ch12 unknown model visibility', unknown_ok, 'unknown model is surfaced in cost summary'),
        Check('Ch12 observe uses production pricing',
              'from harness_py_pro.token_budget import MODEL_PRICING' in observe_text,
              'example imports MODEL_PRICING from production module'),
        Check('Ch12 run_all_cases uses case runners',
              'spec_from_file_location' in run_all_text and 'run_refactor' in run_all_text and 'run_compliance' in run_all_text,
              'full experiment executes the same runners as the chapters'),
    ]


def main() -> bool:
    checks = []
    checks.extend(check_ch9())
    checks.extend(check_ch10())
    checks.extend(check_ch11())
    checks.extend(check_ch12())

    passed = 0
    print('=' * 72)
    print('Ch9-Ch12 Harness Kernel Gate')
    print('=' * 72)
    for item in checks:
        mark = 'PASS' if item.ok else 'FAIL'
        print(f'[{mark}] {item.name}')
        print(f'       {item.detail}')
        if item.ok:
            passed += 1
    print('=' * 72)
    print(f'Result: {passed}/{len(checks)} passed')
    return passed == len(checks)


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
