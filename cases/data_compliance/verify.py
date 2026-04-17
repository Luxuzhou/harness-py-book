"""
数据合规案例验证脚本。

逐项检查 TASK.md 列出的 6 项验收。可离线运行，不需要 API key。
返回值：成功时返回 True，失败时打印详情并返回 False。

用法：
    python cases/data_compliance/verify.py
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
TARGET = CASE_DIR / 'target_service'


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''


def _collect_py(root: Path) -> list[Path]:
    return [p for p in root.rglob('*.py') if '__pycache__' not in p.parts]


def check_sql_parameterized() -> tuple[bool, list[str]]:
    """验收1：SQL 必须参数化。

    判定：在 services/ 下不得出现把变量直接插入 SELECT/WHERE/IN/LIKE 的 f-string。
    合规写法必须把参数放到 execute() 的第二个参数里。
    """
    findings: list[str] = []
    sql_token_re = re.compile(
        r'(?i)f["\'][^"\']*\b(select|insert|update|delete|where|from|in|like|order by)\b'
    )
    concat_in_where_re = re.compile(
        r'append\s*\(\s*f["\'][^"\']*\b(where|and|or|in|like)\b[^"\']*\{',
        re.IGNORECASE,
    )
    for py in _collect_py(TARGET / 'app' / 'services'):
        text = _read(py)
        for pat in (sql_token_re, concat_in_where_re):
            for m in pat.finditer(text):
                line = text[:m.start()].count('\n') + 1
                findings.append(f'{py.relative_to(CASE_DIR)}:{line} SQL 字符串拼接')
    # 同一行重复命中只保留一个
    uniq = sorted(set(findings))
    return (not uniq), uniq[:10]  # 最多报告 10 条


def check_pii_masking_defined() -> tuple[bool, list[str]]:
    """验收2：PII 脱敏函数必须存在并被调用。"""
    findings: list[str] = []
    sec_py = TARGET / 'app' / 'core' / 'security.py'
    if not sec_py.exists():
        return False, [f'{sec_py.relative_to(CASE_DIR)} 不存在']
    text = _read(sec_py)
    if 'def mask_pii' not in text:
        findings.append('mask_pii() 函数未定义')
    # 检查 endpoints 是否调用 mask_pii
    endpoints_dir = TARGET / 'app' / 'api'
    called = False
    for py in _collect_py(endpoints_dir):
        if 'mask_pii' in _read(py):
            called = True
            break
    if not called:
        findings.append('mask_pii() 在 app/api/ 中未被引用')
    return (not findings), findings


def check_audit_middleware_registered() -> tuple[bool, list[str]]:
    """验收3：审计中间件必须存在并注册。"""
    findings: list[str] = []
    audit_py = TARGET / 'app' / 'middleware' / 'audit_log.py'
    if not audit_py.exists():
        return False, [f'{audit_py.relative_to(CASE_DIR)} 不存在']
    if 'AuditLogMiddleware' not in _read(audit_py):
        findings.append('AuditLogMiddleware 类未定义')
    main_py = TARGET / 'app' / 'main.py'
    main_text = _read(main_py)
    if 'AuditLogMiddleware' not in main_text:
        findings.append('main.py 未注册 AuditLogMiddleware')
    return (not findings), findings


def check_sandbox_config_exists() -> tuple[bool, list[str]]:
    """验收4：沙箱/文件策略配置文件存在。"""
    findings: list[str] = []
    candidates = [
        TARGET / 'app' / 'core' / 'sandbox_config.py',
        CASE_DIR / 'run.py',
    ]
    ok = False
    for p in candidates:
        if p.exists() and ('FilesystemPolicy' in _read(p)
                           or 'allowed_paths' in _read(p)):
            ok = True
            break
    if not ok:
        findings.append('未发现沙箱/文件策略声明（FilesystemPolicy 或 allowed_paths）')
    return ok, findings


def check_network_policy() -> tuple[bool, list[str]]:
    """验收5：网络隔离声明。"""
    findings: list[str] = []
    run_text = _read(CASE_DIR / 'run.py')
    if 'network_isolated=True' not in run_text:
        findings.append('run.py 未声明 network_isolated=True')
    return (not findings), findings


def check_pytest_passes() -> tuple[bool, list[str]]:
    """验收6：target_service/tests/ 全部通过。"""
    tests_dir = TARGET / 'tests'
    if not tests_dir.exists():
        return False, [f'{tests_dir.relative_to(CASE_DIR)} 不存在']
    # 只跑一次 pytest，不超时
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', str(tests_dir), '-q'],
            cwd=str(TARGET),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, ['pytest 超时（>120s）']
    except FileNotFoundError:
        return False, ['pytest 未安装']
    if result.returncode != 0:
        tail = '\n'.join(result.stdout.splitlines()[-10:])
        return False, [f'pytest 失败：\n{tail}']
    return True, []


def main() -> bool:
    checks = [
        ('1. SQL 参数化', check_sql_parameterized),
        ('2. PII 脱敏函数', check_pii_masking_defined),
        ('3. 审计中间件已注册', check_audit_middleware_registered),
        ('4. 沙箱/文件策略', check_sandbox_config_exists),
        ('5. 网络隔离', check_network_policy),
        ('6. 单元测试通过', check_pytest_passes),
    ]

    print('=' * 60)
    print('数据合规案例 — 验收检查')
    print('=' * 60)

    all_pass = True
    for name, fn in checks:
        try:
            ok, findings = fn()
        except Exception as e:
            ok, findings = False, [f'检查脚本异常: {type(e).__name__}: {e}']
        mark = 'PASS' if ok else 'FAIL'
        print(f'[{mark}] {name}')
        for f in findings:
            print(f'       - {f}')
        if not ok:
            all_pass = False

    print('=' * 60)
    print('结果:', 'ALL PASS' if all_pass else 'HAS FAILURES')
    return all_pass


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
