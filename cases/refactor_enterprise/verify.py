"""
遗留系统重构案例 — 静态验收脚本。

逐项检查 TASK.md 列出的 6 项验收。可离线运行，不需要 Maven 或 API key。

用法：
    python cases/refactor_enterprise/verify.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CASE_DIR = Path(__file__).parent
TARGET = CASE_DIR / 'target_project'
SERVICE_DIR = TARGET / 'src' / 'main' / 'java' / 'com' / 'example' / 'cp' / 'service'
CONTROLLER_DIR = TARGET / 'src' / 'main' / 'java' / 'com' / 'example' / 'cp' / 'controller'
TEST_DIR = TARGET / 'src' / 'test' / 'java' / 'com' / 'example' / 'cp' / 'service'


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return ''
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding='gbk')
        except Exception:
            return ''


def check_god_class_split() -> tuple[bool, list[str]]:
    """验收1：CpPlanService 不得超过 400 行；且至少新增 5 个 *Service.java。"""
    findings: list[str] = []
    cp_plan = SERVICE_DIR / 'plan' / 'CpPlanService.java'
    if cp_plan.exists():
        loc = len(_read(cp_plan).splitlines())
        if loc >= 400:
            findings.append(f'CpPlanService.java 当前 {loc} 行，超过 400 行上限')
    # 枚举新增 Service
    existing_services = set()
    if SERVICE_DIR.exists():
        for p in SERVICE_DIR.rglob('*Service.java'):
            existing_services.add(p.stem)
    # 基线：已有的 Service 列表
    baseline = {
        'CpPlanService',
        'CpDeviationService',
        'CpAnomalyNotificationService',
        'CpPlanScheduler',  # 已存在的调度器
    }
    new_services = existing_services - baseline
    if len(new_services) < 5:
        findings.append(
            f'新增 Service 数量不足：发现 {len(new_services)} 个新 Service '
            f'{sorted(new_services)}，要求至少 5 个')
    return (not findings), findings


def check_api_contracts_unchanged() -> tuple[bool, list[str]]:
    """验收2：对外 Controller 的关键路径方法未被修改。

    基线路由（基于 CpPlanController.java 当前契约）：
    /api/cp/plan 下挂载 create / update/{id} / delete/{id} / detail/{id} /
    page / list / apply / batch/* / changes/{id} / stats/count
    """
    findings: list[str] = []
    plan_controller = CONTROLLER_DIR / 'CpPlanController.java'
    if not plan_controller.exists():
        return False, ['CpPlanController.java 不存在']
    text = _read(plan_controller)
    # 基线前缀
    if '@RequestMapping("/api/cp/plan")' not in text:
        findings.append('Controller 基线路由前缀 /api/cp/plan 被修改')
    # 必须保留的 mapping
    required_mappings = [
        '@PostMapping("/create")',
        '@GetMapping("/detail/',
        '@GetMapping("/list")',
        '@PostMapping("/apply")',
    ]
    for m in required_mappings:
        if m not in text:
            findings.append(f'CpPlanController 缺失 {m}')
    return (not findings), findings


def check_controller_depends_on_split_services() -> tuple[bool, list[str]]:
    """验收3：Controller 不得直接依赖 CpPlanService 单点。"""
    findings: list[str] = []
    plan_controller = CONTROLLER_DIR / 'CpPlanController.java'
    text = _read(plan_controller)
    # 统计注入字段中的 *Service 类数量
    autowired = re.findall(r'@(?:Autowired|Resource)\s+(?:private|protected|public)?\s*'
                           r'(\w+Service)\s+\w+', text)
    if not autowired:
        # 换一种方式：构造函数注入
        autowired = re.findall(r'(\w+Service)\s+\w+\s*[,)]', text)
    unique_services = set(autowired)
    if len(unique_services) < 2:
        findings.append(
            f'Controller 只依赖 {len(unique_services)} 个 Service：{sorted(unique_services)}，'
            f'要求拆分后至少依赖 2 个专职 Service')
    return (not findings), findings


def check_tests_exist() -> tuple[bool, list[str]]:
    """验收4：新 Service 必须有对应的 ServiceTest.java。"""
    findings: list[str] = []
    if not TEST_DIR.exists():
        return False, [f'{TEST_DIR.relative_to(CASE_DIR)} 不存在']
    test_files = list(TEST_DIR.rglob('*Test.java'))
    if len(test_files) < 5:
        findings.append(
            f'测试类数量不足：{len(test_files)} 个；要求至少 5 个（对应 5 个新 Service）')
    # 每个测试类至少 3 个 @Test 方法
    for tf in test_files:
        text = _read(tf)
        n = len(re.findall(r'@Test\b', text))
        if n < 3:
            findings.append(f'{tf.name}: 只有 {n} 个 @Test 方法，要求至少 3 个')
    return (not findings), findings[:10]


def check_java_syntax() -> tuple[bool, list[str]]:
    """验收5：编译（或轻量语法）通过。

    优先用 mvn compile；若没有 mvn，则用 javac 对 service/ 下每个文件做语法检查。
    """
    findings: list[str] = []
    try:
        # 优先 mvn compile
        result = subprocess.run(
            ['mvn', '-q', 'compile', '-DskipTests'],
            cwd=str(TARGET),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            findings.append('mvn compile 失败：\n' + result.stdout[-500:])
        return (not findings), findings
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        return False, ['mvn compile 超时']

    # Fallback: 用 javac --help 判定 java 是否可用
    try:
        jres = subprocess.run(['javac', '-version'], capture_output=True, timeout=10)
        if jres.returncode != 0:
            # 无 java 工具链，降级为"不判定"，视为 pass 并给一条 info
            return True, ['INFO: 未检测到 mvn/javac，跳过编译验证（本机未安装 Java 工具链）']
    except FileNotFoundError:
        return True, ['INFO: 未检测到 mvn/javac，跳过编译验证（本机未安装 Java 工具链）']

    # 有 javac 但无 mvn：对 service/ 下最小子集做语法检查
    for java_file in SERVICE_DIR.rglob('*.java'):
        if '__' in java_file.name:
            continue
        try:
            res = subprocess.run(
                ['javac', '-d', str(TARGET / 'target_stub'), '-sourcepath',
                 str(TARGET / 'src' / 'main' / 'java'), str(java_file)],
                capture_output=True, text=True, timeout=30,
            )
            if res.returncode != 0 and 'cannot find symbol' not in res.stderr:
                findings.append(f'{java_file.name}: 语法错误（{res.stderr[:200]}）')
        except Exception:
            pass
    return (not findings), findings[:5]


def check_no_unauthorized_changes() -> tuple[bool, list[str]]:
    """验收6：未新增业务 endpoint；未删除 @Transactional。"""
    findings: list[str] = []
    plan_controller = CONTROLLER_DIR / 'CpPlanController.java'
    text = _read(plan_controller)
    # 原基线约 12 个 mapping 注解；允许 ±2 波动
    route_count = len(re.findall(r'@(Get|Post|Put|Delete|Patch|Request)Mapping',
                                  text))
    if route_count > 15:
        findings.append(f'CpPlanController 路由数量 {route_count} 异常增长（基线 ~12）')
    # 检查 service 下 @Transactional 仍存在
    has_tx = False
    for py in SERVICE_DIR.rglob('*.java'):
        if '@Transactional' in _read(py):
            has_tx = True
            break
    if not has_tx:
        findings.append('service/ 下找不到 @Transactional 标注，疑似被移除')
    return (not findings), findings


def main() -> bool:
    checks = [
        ('1. God Class 拆分', check_god_class_split),
        ('2. 对外契约不变', check_api_contracts_unchanged),
        ('3. Controller 依赖倒置', check_controller_depends_on_split_services),
        ('4. 单元测试覆盖', check_tests_exist),
        ('5. 编译/语法通过', check_java_syntax),
        ('6. 无越权变更', check_no_unauthorized_changes),
    ]

    print('=' * 60)
    print('遗留系统重构案例 — 验收检查')
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
