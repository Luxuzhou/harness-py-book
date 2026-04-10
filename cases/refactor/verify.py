"""
Case 1: 重构验证脚本
====================
检查重构结果是否满足验收标准。
用法: python cases/refactor/verify.py
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

CASE_DIR = Path(__file__).parent
TARGET_DIR = CASE_DIR / 'target_project'
SRC_DIR = TARGET_DIR / 'src'

# 设置临时数据库
tmp = tempfile.mkdtemp()
os.environ['INVENTORY_DB'] = os.path.join(tmp, 'verify.db')


def check_god_class_split():
    """检查God Class是否被拆分。"""
    app_file = SRC_DIR / 'app.py'
    if not app_file.exists():
        return False, 'app.py不存在'

    content = app_file.read_text(encoding='utf-8')
    class_count = content.count('class ')

    # 检查是否有新的Service类文件
    service_files = list(SRC_DIR.glob('*service*.py')) + list(SRC_DIR.glob('*repository*.py'))
    new_classes = []
    for f in SRC_DIR.glob('*.py'):
        if f.name == '__init__.py':
            continue
        fc = f.read_text(encoding='utf-8')
        for line in fc.splitlines():
            if line.strip().startswith('class ') and 'InventoryApp' not in line:
                new_classes.append(line.strip())

    if len(service_files) >= 2 or len(new_classes) >= 3:
        return True, f'已拆分: 发现 {len(service_files)} 个服务文件, {len(new_classes)} 个新类'
    return False, f'拆分不足: 仅发现 {len(service_files)} 个服务文件'


def check_sql_injection():
    """检查SQL字符串拼接是否被消除。"""
    issues = []
    for f in SRC_DIR.glob('*.py'):
        content = f.read_text(encoding='utf-8')
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            if 'f"' in line and ('INSERT' in line or 'SELECT' in line or 'UPDATE' in line or 'DELETE' in line):
                issues.append(f'{f.name}:{i}')
            if "f'" in line and ('INSERT' in line or 'SELECT' in line or 'UPDATE' in line or 'DELETE' in line):
                issues.append(f'{f.name}:{i}')

    if not issues:
        return True, 'SQL字符串拼接已消除'
    return False, f'仍有 {len(issues)} 处SQL拼接: {issues[:5]}'


def check_hardcoded_paths():
    """检查硬编码路径是否被提取。"""
    issues = []
    for f in SRC_DIR.glob('*.py'):
        content = f.read_text(encoding='utf-8')
        for i, line in enumerate(content.splitlines(), 1):
            if 'C:/' in line or 'C:\\\\' in line:
                if '#' not in line.split('C:')[0]:  # 排除注释
                    issues.append(f'{f.name}:{i}')

    if not issues:
        return True, '硬编码路径已清除'
    return False, f'仍有 {len(issues)} 处硬编码路径: {issues[:5]}'


def check_tests():
    """运行测试。"""
    test_dir = TARGET_DIR / 'tests'
    test_files = list(test_dir.glob('test_*.py'))

    if len(test_files) < 2:
        return False, f'测试文件不足: 仅有 {len(test_files)} 个'

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(test_dir), '-v', '--tb=short'],
            capture_output=True, text=True, timeout=60,
            cwd=str(TARGET_DIR),
            env={**os.environ, 'PYTHONPATH': str(SRC_DIR)},
        )
        passed = result.returncode == 0
        # 统计测试数量
        test_count = result.stdout.count(' PASSED') + result.stdout.count(' passed')
        return passed, f'测试{"通过" if passed else "失败"}: {test_count} 个测试\n{result.stdout[-500:]}'
    except Exception as e:
        return False, f'测试运行异常: {e}'


def check_report():
    """检查重构报告。"""
    report = TARGET_DIR / 'refactor_report.md'
    if not report.exists():
        # 也检查case目录
        report = CASE_DIR / 'refactor_report.md'
    if not report.exists():
        return False, 'refactor_report.md 不存在'

    content = report.read_text(encoding='utf-8')
    if len(content) < 200:
        return False, '报告内容过少'
    return True, f'报告存在 ({len(content)} 字符)'


def main():
    checks = [
        ('God Class拆分', check_god_class_split),
        ('SQL注入修复', check_sql_injection),
        ('硬编码清除', check_hardcoded_paths),
        ('测试通过', check_tests),
        ('重构报告', check_report),
    ]

    print('='*50)
    print('Case 1: 遗留系统重构 — 验收检查')
    print('='*50)

    passed = 0
    total = len(checks)

    for name, check_fn in checks:
        try:
            ok, detail = check_fn()
        except Exception as e:
            ok, detail = False, f'检查异常: {e}'

        status = '✓ PASS' if ok else '✗ FAIL'
        print(f'\n{status}  {name}')
        print(f'  {detail}')
        if ok:
            passed += 1

    print(f'\n{"="*50}')
    print(f'结果: {passed}/{total} 通过')
    print(f'{"="*50}')
    return passed == total


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
