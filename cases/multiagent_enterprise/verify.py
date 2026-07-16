"""
Chapter 11 multi-agent orchestration verifier.

This script is intentionally stricter than a simple "file exists" check.
The chapter experiment is considered converged only when the generated
plan/report are fresh enough to contain an explicit PASS marker and the
expected cross-project implementation/test artifacts are present.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - local environment guard
    yaml = None  # type: ignore


CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
JAVA_ROOT = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
PY_ROOT = REPO_ROOT / 'cases' / 'data_compliance' / 'target_service'
SPEC_DIR = CASE_DIR / 'spec'


def _check(label, fn):
    try:
        ok, detail = fn()
    except Exception as exc:  # pragma: no cover - verifier robustness
        ok, detail = False, f'check crashed: {type(exc).__name__}: {exc}'
    return label, ok, detail


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_anchors_exist():
    if not JAVA_ROOT.exists():
        return False, f'Java project missing: {JAVA_ROOT}'
    if not PY_ROOT.exists():
        return False, f'Python service missing: {PY_ROOT}'
    java_count = len(list(JAVA_ROOT.rglob('*.java')))
    py_count = len(list(PY_ROOT.rglob('*.py')))
    if java_count < 50:
        return False, f'Java source count too small: {java_count}'
    if py_count < 10:
        return False, f'Python source count too small: {py_count}'
    return True, f'anchors ready: {java_count} Java files, {py_count} Python files'


def check_orchestration_files():
    required = [
        CASE_DIR / 'TASK.md',
        CASE_DIR / 'CLAUDE.md',
        CASE_DIR / 'run.py',
        CASE_DIR / 'verify.py',
        SPEC_DIR / 'requirement.md',
        SPEC_DIR / 'api_contract.yaml',
        SPEC_DIR / 'architecture.md',
        CASE_DIR / 'roles' / 'architect.md',
        CASE_DIR / 'roles' / 'java_developer.md',
        CASE_DIR / 'roles' / 'python_developer.md',
        CASE_DIR / 'roles' / 'qa_engineer.md',
    ]
    missing = [_rel(p) for p in required if not p.exists()]
    if missing:
        return False, 'missing files: ' + ', '.join(missing)
    return True, f'orchestration skeleton complete ({len(required)} files)'


def check_harness_controls():
    text = (CASE_DIR / 'run.py').read_text(encoding='utf-8')
    required_tokens = [
        'round_plan=',
        'parallel_groups=',
        "sandbox_mode='bypass'",
        'network_isolated=True',
        'allowed_paths=',
        'filesystem_roots=',
        'read_only_paths=',
        'acceptance_check',
        'acceptance_commands=',
    ]
    missing = [token for token in required_tokens if token not in text]
    if missing:
        return False, 'missing Harness controls: ' + ', '.join(missing)
    if 'run_acceptance' in text:
        return False, 'run.py references obsolete tool name run_acceptance'
    return True, 'round plan, parallel groups, path boundaries and acceptance gate configured'


def check_python_syntax():
    targets = [
        CASE_DIR / 'run.py',
        CASE_DIR / 'verify.py',
        PY_ROOT / 'app' / 'main.py',
    ]
    errors: list[str] = []
    for path in targets:
        if not path.exists():
            errors.append(f'missing: {_rel(path)}')
            continue
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except SyntaxError as exc:
            errors.append(f'{_rel(path)} line {exc.lineno}: {exc.msg}')
    if errors:
        return False, 'syntax errors: ' + '; '.join(errors)
    return True, 'orchestration scripts and Python entrypoint parse'


def check_contract_consistency():
    contract_file = SPEC_DIR / 'api_contract.yaml'
    if yaml is None:
        return False, 'PyYAML is not installed'
    contract = yaml.safe_load(contract_file.read_text(encoding='utf-8'))
    schemas = set((contract.get('components', {}).get('schemas') or {}).keys())
    expected = {
        'AnomalyRuleCreateRequest',
        'AnomalyRuleResponse',
        'AnomalyEventCreateRequest',
        'AnomalyEventResponse',
        'DeviationPoint',
        'ErrorResponse',
    }
    missing_contract = expected - schemas
    if missing_contract:
        return False, 'contract missing schemas: ' + ', '.join(sorted(missing_contract))

    py_schemas = PY_ROOT / 'app' / 'models' / 'schemas.py'
    tree = ast.parse(py_schemas.read_text(encoding='utf-8'))
    py_classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    expected_py = expected - {'AnomalyRuleCreateRequest'}
    missing_py = expected_py - py_classes
    if missing_py:
        return False, 'Python schemas missing classes: ' + ', '.join(sorted(missing_py))
    return True, f'OpenAPI schemas and Python models aligned on {len(expected_py)} response/request classes'


def check_cross_project_artifacts():
    java_client_dir = JAVA_ROOT / 'src' / 'main' / 'java' / 'com' / 'example' / 'cp' / 'client'
    java_clients = list(java_client_dir.glob('*.java')) if java_client_dir.exists() else []
    if not java_clients:
        return False, 'Java client artifact missing under src/main/java/com/example/cp/client'
    java_text = '\n'.join(p.read_text(encoding='utf-8', errors='ignore') for p in java_clients)
    if not re.search(r'(RestTemplate|WebClient|HttpClient|OkHttpClient)', java_text):
        return False, 'Java client exists but no HTTP client usage was detected'

    py_client = PY_ROOT / 'app' / 'clients' / 'java_api_client.py'
    if not py_client.exists():
        return False, 'Python Java API client missing'
    py_text = py_client.read_text(encoding='utf-8')
    for token in ['get_anomaly_rule', 'create_anomaly_event', 'X-Service-Token']:
        if token not in py_text:
            return False, f'Python Java API client missing token: {token}'
    return True, 'Java-to-Python and Python-to-Java client artifacts are present'


def check_architect_plan():
    plan_file = CASE_DIR / 'implementation_plan.md'
    if not plan_file.exists():
        return False, 'implementation_plan.md missing'
    content = plan_file.read_text(encoding='utf-8')
    required_terms = ['Java', 'Python', '测试', '风险']
    missing = [term for term in required_terms if term not in content]
    if missing:
        return False, 'plan missing terms: ' + ', '.join(missing)
    return True, f'implementation_plan.md present ({len(content)} chars)'


def check_test_report():
    report_file = CASE_DIR / 'test_report.md'
    if not report_file.exists():
        return False, 'test_report.md missing'
    content = report_file.read_text(encoding='utf-8')
    if len(content) < 100:
        return False, f'test_report.md too short ({len(content)} chars)'
    if 'FINAL_STATUS: PASS' not in content:
        return False, 'test_report.md missing FINAL_STATUS: PASS'

    bad_patterns = [
        r'FINAL_STATUS:\s*FAIL',
        r'(?:Failed|failures?)\s*[:：]\s*[1-9]\d*',
        r'(?:Known defects|Defects)\s*[:：]\s*[1-9]\d*',
        r'(?:失败|已知代码缺陷|缺陷)[^0-9\n]{0,20}[1-9]\d*',
    ]
    for pattern in bad_patterns:
        if re.search(pattern, content, flags=re.IGNORECASE):
            return False, f'test_report.md still records failing items: {pattern}'
    contradiction_patterns = [
        r'##\s*已知问题(?!\s*[:：]?\s*(无|None|0))',
        r'(?:建议修复|需由.*补充|优先级\s*[:：]\s*P[0-9])',
        r'(?:known issues?|recommended fix|priority\s*[:：]\s*P[0-9])',
    ]
    for pattern in contradiction_patterns:
        if re.search(pattern, content, flags=re.IGNORECASE):
            return False, f'test_report.md claims PASS but still contains unresolved issue text: {pattern}'

    required_python_tests = [
        PY_ROOT / 'tests' / 'test_contract_consistency.py',
        PY_ROOT / 'tests' / 'test_java_api_client.py',
    ]
    missing = [_rel(p) for p in required_python_tests if not p.exists()]

    java_test_candidates = [
        JAVA_ROOT / 'src' / 'test' / 'java' / 'com' / 'example' / 'cp' / 'client' / 'PythonServiceClientTest.java',
        JAVA_ROOT / 'src' / 'test' / 'java' / 'com' / 'example' / 'cp' / 'client' / 'PythonAnalysisClientTest.java',
    ]
    if not any(path.exists() for path in java_test_candidates):
        missing.append(_rel(java_test_candidates[0]))
    if missing:
        return False, 'missing QA test artifacts: ' + ', '.join(missing)

    return True, f'test_report.md PASS with required QA artifacts ({len(content)} chars)'


def main() -> bool:
    checks = [
        ('1. anchor projects', check_anchors_exist),
        ('2. orchestration skeleton', check_orchestration_files),
        ('3. Harness controls', check_harness_controls),
        ('4. Python syntax', check_python_syntax),
        ('5. contract consistency', check_contract_consistency),
        ('6. cross-project artifacts', check_cross_project_artifacts),
        ('7. architect plan', check_architect_plan),
        ('8. QA report', check_test_report),
    ]

    print('=' * 60)
    print('Chapter 11 multi-agent orchestration acceptance check')
    print('=' * 60)

    passed = 0
    for name, fn in checks:
        _, ok, detail = _check(name, fn)
        mark = 'PASS' if ok else 'FAIL'
        print(f'\n[{mark}] {name}')
        for line in str(detail).splitlines():
            print(f'       {line}')
        if ok:
            passed += 1

    print(f'\n{"=" * 60}')
    print(f'Result: {passed}/{len(checks)} passed')
    return passed == len(checks)


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
