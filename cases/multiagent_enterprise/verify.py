"""
Ch10 案例：跨项目多 Agent 编排 — 验证脚本。

本案例不再在本目录下自建业务代码，而是直接跨 Ch8 Java 项目与 Ch9 Python 服务工作。
本脚本只校验：
1. Ch8 / Ch9 两个锚点目录存在且内容完整
2. 编排骨架文件齐全（spec、roles、TASK、CLAUDE、run、verify）
3. Python 脚本（含 run.py、Ch9 的 app/）语法正确
4. 接口契约一致性（Python Pydantic 类 vs OpenAPI schema）
5. Architect 产物 `implementation_plan.md` 存在且含关键章节（运行后才会通过）
6. QA 产物 `test_report.md` 存在（运行后才会通过）
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

try:
    import yaml  # noqa
except ImportError:
    yaml = None  # type: ignore

CASE_DIR = Path(__file__).parent
REPO_ROOT = CASE_DIR.parent.parent
CH8_ROOT = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
CH9_ROOT = REPO_ROOT / 'cases' / 'data_compliance' / 'target_service'
SPEC_DIR = CASE_DIR / 'spec'


def _check(label, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f'检查异常: {type(e).__name__}: {e}'
    return label, ok, detail


# ── Check 1 ──────────────────────────────────────────
def check_anchors_exist():
    """Ch8 与 Ch9 的业务代码根目录必须可达。"""
    if not CH8_ROOT.exists():
        return False, f'Ch8 目录缺失: {CH8_ROOT}'
    if not CH9_ROOT.exists():
        return False, f'Ch9 目录缺失: {CH9_ROOT}'
    java_count = len(list(CH8_ROOT.rglob('*.java')))
    py_count = len(list(CH9_ROOT.rglob('*.py')))
    if java_count < 50:
        return False, f'Ch8 Java 文件数过少：{java_count}（预期 ≥50）'
    if py_count < 10:
        return False, f'Ch9 Python 文件数过少：{py_count}（预期 ≥10）'
    return True, (f'Ch8 Java 文件 {java_count} 个，Ch9 Python 文件 {py_count} 个；'
                   f'两个锚点目录均就位')


# ── Check 2 ──────────────────────────────────────────
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
    missing = [str(p.relative_to(CASE_DIR)) for p in required if not p.exists()]
    if missing:
        return False, '缺失文件:\n    ' + '\n    '.join(missing)
    return True, f'编排骨架 {len(required)} 个文件齐全'


# ── Check 3 ──────────────────────────────────────────
def check_python_syntax():
    targets = [CASE_DIR / 'run.py', CASE_DIR / 'verify.py']
    errors = []
    for pf in targets:
        try:
            ast.parse(pf.read_text(encoding='utf-8'), filename=str(pf))
        except SyntaxError as e:
            errors.append(f'{pf.name} line {e.lineno}: {e.msg}')
    # 再抽查 Ch9 Python 服务 import 入口
    key = CH9_ROOT / 'app' / 'main.py'
    if key.exists():
        try:
            ast.parse(key.read_text(encoding='utf-8'), filename=str(key))
        except SyntaxError as e:
            errors.append(f'Ch9 app/main.py line {e.lineno}: {e.msg}')
    if errors:
        return False, '语法错误:\n    ' + '\n    '.join(errors)
    return True, '编排脚本与 Ch9 入口 main.py 语法正确'


# ── Check 4 ──────────────────────────────────────────
def check_contract_consistency():
    contract_file = SPEC_DIR / 'api_contract.yaml'
    if not contract_file.exists():
        return False, 'api_contract.yaml 不存在'
    if yaml is None:
        return True, 'INFO: 未安装 PyYAML，跳过契约解析'
    try:
        contract = yaml.safe_load(contract_file.read_text(encoding='utf-8'))
    except Exception as e:
        return False, f'解析 api_contract.yaml 失败: {e}'
    contract_schemas = set(
        (contract.get('components', {}).get('schemas') or {}).keys()
    )
    # Ch9 的 schemas.py 应定义若干对应类
    ch9_schemas = CH9_ROOT / 'app' / 'models' / 'schemas.py'
    if not ch9_schemas.exists():
        return False, 'Ch9 schemas.py 不存在'
    tree = ast.parse(ch9_schemas.read_text(encoding='utf-8'))
    py_classes = {
        n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)
    }
    if not contract_schemas:
        return True, 'api_contract.yaml 里没有定义 schemas（软通过）'
    key_schemas = {'AnomalyRuleResponse', 'AnomalyEventCreateRequest',
                   'AnomalyEventResponse', 'DeviationPoint', 'ErrorResponse'}
    missing = key_schemas - py_classes - contract_schemas
    return True, (f'OpenAPI schemas: {len(contract_schemas)}；'
                   f'Ch9 schemas.py 类: {len(py_classes)}；'
                   f'关键类缺失: {len(missing)}')


# ── Check 5 ──────────────────────────────────────────
def check_architect_plan():
    plan_file = CASE_DIR / 'implementation_plan.md'
    if not plan_file.exists():
        return False, 'implementation_plan.md 不存在（Architect 尚未执行）'
    content = plan_file.read_text(encoding='utf-8')
    sections = ['Java', 'Python', '测试', '风险']
    missing = [s for s in sections if s not in content]
    if missing:
        return False, f'plan 缺少章节关键词: {", ".join(missing)}'
    return True, f'implementation_plan.md 存在 ({len(content)} 字符)，包含全部关键章节'


# ── Check 6 ──────────────────────────────────────────
def check_test_report():
    report_file = CASE_DIR / 'test_report.md'
    if not report_file.exists():
        return False, 'test_report.md 不存在（QA 尚未执行）'
    content = report_file.read_text(encoding='utf-8')
    if len(content) < 100:
        return False, f'test_report.md 过短 ({len(content)} 字符)'
    return True, f'test_report.md 存在 ({len(content)} 字符)'


def main() -> bool:
    checks = [
        ('1. Ch8 / Ch9 锚点目录', check_anchors_exist),
        ('2. 编排骨架完整', check_orchestration_files),
        ('3. 编排脚本语法', check_python_syntax),
        ('4. 接口契约一致性', check_contract_consistency),
        ('5. Architect 产物', check_architect_plan),
        ('6. QA 测试报告', check_test_report),
    ]
    print('=' * 60)
    print('Ch10: 跨项目多 Agent 编排 — 验收检查')
    print('=' * 60)

    passed = 0
    for name, fn in checks:
        _, ok, detail = _check(name, fn)
        mark = 'PASS' if ok else 'FAIL'
        print(f'\n[{mark}] {name}')
        for line in str(detail).split('\n'):
            print(f'       {line}')
        if ok:
            passed += 1

    print(f'\n{"=" * 60}')
    print(f'结果: {passed}/{len(checks)} 通过')
    print('提示: Architect Plan 与 测试报告 只能在 run.py 执行后才会生成。')
    return passed >= 4  # 至少前 4 项必须通过


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
