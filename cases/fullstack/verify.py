"""
Case 3: 多Agent全栈开发 — 验证脚本
====================================
用法: python cases/fullstack/verify.py
"""

import os
import re
import sys
import subprocess
from pathlib import Path

CASE_DIR = Path(__file__).parent
OUTPUT_DIR = CASE_DIR / 'output'


def check_files_exist():
    """检查必要文件是否存在。"""
    required = ['task_cli.py', 'task_store.py', 'plan.md', 'review.md']
    missing = [f for f in required if not (OUTPUT_DIR / f).exists()]
    test_dir = OUTPUT_DIR / 'tests'
    has_tests = test_dir.exists() and list(test_dir.glob('test_*.py'))

    if missing:
        return False, f'缺少文件: {", ".join(missing)}'
    if not has_tests:
        return False, '缺少测试文件'
    return True, f'全部文件存在，测试目录有 {len(list(test_dir.glob("test_*.py")))} 个测试文件'


def check_add_task():
    """测试添加任务功能。"""
    cli = OUTPUT_DIR / 'task_cli.py'
    if not cli.exists():
        return False, 'task_cli.py不存在'

    # 清理旧数据
    for db in OUTPUT_DIR.glob('*.json'):
        if 'task' in db.name.lower():
            db.unlink(missing_ok=True)

    try:
        result = subprocess.run(
            [sys.executable, str(cli), 'add', 'Buy milk for verification'],
            capture_output=True, text=True, timeout=10,
            cwd=str(OUTPUT_DIR),
        )
        if result.returncode == 0:
            return True, f'添加成功: {result.stdout.strip()}'
        return False, f'退出码 {result.returncode}: {result.stderr.strip()}'
    except Exception as e:
        return False, f'执行异常: {e}'


def check_list_tasks():
    """测试列出任务功能。"""
    cli = OUTPUT_DIR / 'task_cli.py'
    if not cli.exists():
        return False, 'task_cli.py不存在'

    try:
        result = subprocess.run(
            [sys.executable, str(cli), 'list'],
            capture_output=True, text=True, timeout=10,
            cwd=str(OUTPUT_DIR),
        )
        if result.returncode == 0 and ('milk' in result.stdout.lower() or 'Buy' in result.stdout):
            return True, f'列出成功: {result.stdout.strip()[:200]}'
        return False, f'列出失败或不包含预期任务: {result.stdout.strip()[:200]}'
    except Exception as e:
        return False, f'执行异常: {e}'


def check_done_task():
    """测试完成任务功能。"""
    cli = OUTPUT_DIR / 'task_cli.py'
    if not cli.exists():
        return False, 'task_cli.py不存在'

    try:
        result = subprocess.run(
            [sys.executable, str(cli), 'done', '1'],
            capture_output=True, text=True, timeout=10,
            cwd=str(OUTPUT_DIR),
        )
        if result.returncode == 0:
            return True, f'完成成功: {result.stdout.strip()}'
        return False, f'退出码 {result.returncode}: {result.stderr.strip()}'
    except Exception as e:
        return False, f'执行异常: {e}'


def check_delete_task():
    """测试删除任务功能。"""
    cli = OUTPUT_DIR / 'task_cli.py'
    if not cli.exists():
        return False, 'task_cli.py不存在'

    try:
        result = subprocess.run(
            [sys.executable, str(cli), 'delete', '1'],
            capture_output=True, text=True, timeout=10,
            cwd=str(OUTPUT_DIR),
        )
        if result.returncode == 0:
            return True, f'删除成功: {result.stdout.strip()}'
        return False, f'退出码 {result.returncode}: {result.stderr.strip()}'
    except Exception as e:
        return False, f'执行异常: {e}'


def check_tests_pass():
    """运行测试。"""
    test_dir = OUTPUT_DIR / 'tests'
    if not test_dir.exists():
        return False, '测试目录不存在'

    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(test_dir), '-v', '--tb=short'],
            capture_output=True, text=True, timeout=30,
            cwd=str(OUTPUT_DIR),
        )
        passed = result.returncode == 0
        return passed, f'测试{"通过" if passed else "失败"}\n{result.stdout[-500:]}'
    except Exception as e:
        return False, f'测试运行异常: {e}'


def check_evaluator_score():
    """检查Evaluator评分。"""
    review = OUTPUT_DIR / 'review.md'
    if not review.exists():
        return False, 'review.md不存在'

    content = review.read_text(encoding='utf-8')
    score_match = re.search(r'(\d+)\s*/\s*100', content)
    if not score_match:
        return False, '未找到评分'

    score = int(score_match.group(1))
    passed = score >= 70
    verdict = 'PASS' if 'PASS' in content.upper() else 'FAIL'
    return passed, f'Evaluator评分: {score}/100 ({verdict})'


def main():
    checks = [
        ('文件完整性', check_files_exist),
        ('添加任务', check_add_task),
        ('列出任务', check_list_tasks),
        ('完成任务', check_done_task),
        ('删除任务', check_delete_task),
        ('测试通过', check_tests_pass),
        ('Evaluator评分', check_evaluator_score),
    ]

    print('='*50)
    print('Case 3: 多Agent全栈开发 — 验收检查')
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
