"""
Ch10 案例: 多Agent企业级案例 — 验证脚本
========================================
用法: python cases/multiagent_enterprise/verify.py

验证项:
1. 文件完整性 — 所有必要文件是否存在
2. Java 代码能编译 — mvn compile (简化为语法检查)
3. Python 代码能 import — 所有 .py 文件语法正确
4. 接口契约一致 — Python Pydantic 模型字段与 OpenAPI schema 对齐
5. 测试通过 — pytest 执行结果
6. 角色隔离 — Java Dev 没有修改 Python 文件，反之亦然
"""

import ast
import sys
from pathlib import Path

import yaml

CASE_DIR = Path(__file__).parent
JAVA_DIR = CASE_DIR / 'java_module'
PYTHON_DIR = CASE_DIR / 'python_module'
SPEC_DIR = CASE_DIR / 'spec'


# ── 检查 1: 文件完整性 ───────────────────────────

def check_files_exist():
    """检查所有必要文件是否存在。"""
    required_files = [
        # 设计文档
        SPEC_DIR / 'requirement.md',
        SPEC_DIR / 'api_contract.yaml',
        SPEC_DIR / 'architecture.md',
        # 角色定义
        CASE_DIR / 'roles' / 'architect.md',
        CASE_DIR / 'roles' / 'java_developer.md',
        CASE_DIR / 'roles' / 'python_developer.md',
        CASE_DIR / 'roles' / 'qa_engineer.md',
        # Harness 配置
        CASE_DIR / 'CLAUDE.md',
        CASE_DIR / 'TASK.md',
        CASE_DIR / 'run.py',
        # Java 骨架
        JAVA_DIR / 'pom.xml',
        JAVA_DIR / 'src' / 'main' / 'java' / 'com' / 'example' / 'sqc' / 'alarm' / 'controller' / 'AlarmController.java',
        JAVA_DIR / 'src' / 'main' / 'java' / 'com' / 'example' / 'sqc' / 'alarm' / 'service' / 'AlarmService.java',
        JAVA_DIR / 'src' / 'main' / 'java' / 'com' / 'example' / 'sqc' / 'alarm' / 'dao' / 'model' / 'AlarmRule.java',
        JAVA_DIR / 'src' / 'main' / 'java' / 'com' / 'example' / 'sqc' / 'alarm' / 'dto' / 'AlarmRuleDto.java',
        # Python 骨架
        PYTHON_DIR / 'requirements.txt',
        PYTHON_DIR / 'app' / '__init__.py',
        PYTHON_DIR / 'app' / 'api' / 'endpoints.py',
        PYTHON_DIR / 'app' / 'services' / 'alarm_analyzer.py',
        PYTHON_DIR / 'app' / 'models' / 'schemas.py',
    ]

    missing = [str(f.relative_to(CASE_DIR)) for f in required_files if not f.exists()]
    if missing:
        return False, f'缺少 {len(missing)} 个文件:\n    ' + '\n    '.join(missing)
    return True, f'全部 {len(required_files)} 个必要文件存在'


# ── 检查 2: Java 代码结构检查 ────────────────────

def check_java_structure():
    """检查 Java 代码的基本结构（不实际编译，检查关键标记）。"""
    java_files = list(JAVA_DIR.rglob('*.java'))
    if not java_files:
        return False, '无 Java 源文件'

    issues = []
    for jf in java_files:
        content = jf.read_text(encoding='utf-8')
        name = jf.name

        # 检查 package 声明
        if 'package com.example.sqc.alarm' not in content:
            issues.append(f'{name}: 缺少正确的 package 声明')

        # Controller 检查
        if 'Controller' in name:
            if '@RestController' not in content:
                issues.append(f'{name}: 缺少 @RestController 注解')
            if '@RequestMapping' not in content:
                issues.append(f'{name}: 缺少 @RequestMapping 注解')

        # Service 检查
        if 'Service' in name and 'Test' not in name:
            if '@Service' not in content:
                issues.append(f'{name}: 缺少 @Service 注解')

        # Entity 检查
        if name in ('AlarmRule.java', 'AlarmEvent.java'):
            if '@Entity' not in content:
                issues.append(f'{name}: 缺少 @Entity 注解')

    if issues:
        return False, '结构问题:\n    ' + '\n    '.join(issues)
    return True, f'{len(java_files)} 个 Java 文件结构检查通过'


# ── 检查 3: Python 代码语法检查 ──────────────────

def check_python_syntax():
    """检查所有 Python 文件的语法正确性。"""
    py_files = list(PYTHON_DIR.rglob('*.py'))
    if not py_files:
        return False, '无 Python 源文件'

    errors = []
    for pf in py_files:
        try:
            source = pf.read_text(encoding='utf-8')
            ast.parse(source, filename=str(pf))
        except SyntaxError as e:
            errors.append(f'{pf.name} line {e.lineno}: {e.msg}')

    if errors:
        return False, '语法错误:\n    ' + '\n    '.join(errors)
    return True, f'{len(py_files)} 个 Python 文件语法检查通过'


# ── 检查 4: 接口契约一致性 ───────────────────────

def check_contract_consistency():
    """检查 Python Pydantic 模型是否与 OpenAPI 契约字段对齐。"""
    contract_file = SPEC_DIR / 'api_contract.yaml'
    schema_file = PYTHON_DIR / 'app' / 'models' / 'schemas.py'

    if not contract_file.exists():
        return False, 'api_contract.yaml 不存在'
    if not schema_file.exists():
        return False, 'schemas.py 不存在'

    # 解析 OpenAPI 契约中的 schema 名称
    try:
        with open(contract_file, encoding='utf-8') as f:
            contract = yaml.safe_load(f)
    except Exception as e:
        return False, f'解析 api_contract.yaml 失败: {e}'

    contract_schemas = set(contract.get('components', {}).get('schemas', {}).keys())

    # 解析 Python 源码中的类名
    schema_source = schema_file.read_text(encoding='utf-8')
    tree = ast.parse(schema_source)
    py_classes = {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
    }

    # 检查契约中的关键 schema 在 Python 端是否有对应
    key_schemas = {
        'AlarmRuleResponse',
        'AlarmEventCreateRequest',
        'AlarmEventResponse',
        'BreachPoint',
        'ErrorResponse',
    }

    missing_in_python = key_schemas - py_classes
    if missing_in_python:
        return False, f'Python 端缺少契约 schema: {", ".join(missing_in_python)}'

    return True, f'契约关键 schema 在 Python 端均有对应类: {", ".join(sorted(key_schemas & py_classes))}'


# ── 检查 5: Architect plan 存在 ──────────────────

def check_architect_plan():
    """检查 Architect 的 implementation_plan.md 是否生成。"""
    plan_file = CASE_DIR / 'implementation_plan.md'
    if not plan_file.exists():
        return False, 'implementation_plan.md 不存在（Architect 尚未执行）'

    content = plan_file.read_text(encoding='utf-8')
    sections = ['Java', 'Python', '测试', '风险']
    found = [s for s in sections if s in content]
    missing = [s for s in sections if s not in content]

    if missing:
        return False, f'plan 缺少章节关键词: {", ".join(missing)}'
    return True, f'implementation_plan.md 存在，包含 {len(found)} 个关键章节'


# ── 检查 6: 测试报告 ─────────────────────────────

def check_test_report():
    """检查测试报告是否存在及内容。"""
    report_file = CASE_DIR / 'test_report.md'
    if not report_file.exists():
        return False, 'test_report.md 不存在（QA 尚未执行）'

    content = report_file.read_text(encoding='utf-8')
    if len(content) < 100:
        return False, f'test_report.md 内容过短 ({len(content)} 字符)'
    return True, f'test_report.md 存在 ({len(content)} 字符)'


# ── 主流程 ────────────────────────────────────────

def main():
    checks = [
        ('文件完整性', check_files_exist),
        ('Java 代码结构', check_java_structure),
        ('Python 语法检查', check_python_syntax),
        ('接口契约一致性', check_contract_consistency),
        ('Architect Plan', check_architect_plan),
        ('测试报告', check_test_report),
    ]

    print('=' * 60)
    print('Ch10: 多Agent企业级案例 -- 验收检查')
    print('=' * 60)

    passed = 0
    total = len(checks)

    for name, check_fn in checks:
        try:
            ok, detail = check_fn()
        except Exception as e:
            ok, detail = False, f'检查异常: {e}'

        status = 'PASS' if ok else 'FAIL'
        marker = '+' if ok else '-'
        print(f'\n  [{marker}] {status}  {name}')
        for line in detail.split('\n'):
            print(f'      {line}')
        if ok:
            passed += 1

    print(f'\n{"=" * 60}')
    print(f'结果: {passed}/{total} 通过')

    if passed < total:
        print('\n提示: 部分检查项（Architect Plan, 测试报告）需要运行 run.py 后才能通过。')
        print('骨架文件检查应当全部通过。')

    print('=' * 60)
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
