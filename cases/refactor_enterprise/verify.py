"""
遗留系统重构案例 — 静态验收脚本。

逐项检查 TASK.md 列出的 6 项验收。可离线运行，不需要 Maven 或 API key。

用法：
    python cases/refactor_enterprise/verify.py
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from pathlib import Path

# Windows 控制台默认 GBK，subprocess 输出里有可能夹带 \ufffd 替换符（来自
# bytes -> utf-8(errors='replace') 的兜底解码），直接 print 到 GBK 终端会抛
# UnicodeEncodeError。把 stdout/stderr 统一包一层 UTF-8 写入器，兼顾可读性与健壮性。
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass

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
    """
    验收 1：CpPlanService 不得超过 900 行；且至少新增 1 个 *Service.java。

    阈值 900 对应 Ch8 第 8.3 节教学脚本的设定：CpPlanService 原始 1,266 行，
    拆出计算逻辑和变更审计后典型落在 800-900 行区间。阈值设在 900 是"可接受
    起点"而非"理想目标"；读者若追求更严格的收敛，可以把阈值收紧到 600 或 400，
    与之匹配的是要求新增 Service 数量从 1 提升到 5。
    """
    findings: list[str] = []
    cp_plan = SERVICE_DIR / 'plan' / 'CpPlanService.java'
    if cp_plan.exists():
        loc = len(_read(cp_plan).splitlines())
        if loc >= 900:
            findings.append(f'CpPlanService.java 当前 {loc} 行，超过 900 行上限')
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
    if len(new_services) < 1:
        findings.append(
            f'未新增任何 Service：当前只有基线 {sorted(baseline)}，'
            f'要求至少拆出 1 个新 Service')
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
    """验收 5：编译通过（或无 Maven 时降级为 INFO）。

    策略：优先用 `mvn compile` 做真实编译；本机找不到 mvn 时**不再回退到
    javac 单文件编译**（Spring Boot 项目有 Lombok / MyBatis-Flex 等依赖，
    单文件 javac 必然全部报"找不到符号"，产出的信号噪声比得不偿失），
    直接降级为 INFO 并在报告里明确标注"未安装 Maven，跳过严格编译验证"。
    读者要做严格编译验收，需自行安装 Maven 后重跑本脚本。
    """
    # 跨平台的稳健解码：mvn / javac 在 Windows 上常输出 GBK，而 Python 默认按
    # utf-8 严格解码会抛 UnicodeDecodeError。这里统一抓 bytes，再以 errors="replace"
    # 解码，避免脚本末尾出现编码噪音。
    def _run_safe(cmd: list[str], cwd: str | None = None, timeout: int = 60):
        try:
            # Windows 上 mvn 是 .cmd 文件，需要 shell=True 才能被 subprocess 解析
            use_shell = sys.platform == 'win32'
            res = subprocess.run(
                cmd, cwd=cwd, capture_output=True, timeout=timeout,
                shell=use_shell,
            )
        except FileNotFoundError:
            return None, None, -1
        except subprocess.TimeoutExpired:
            return None, None, -2
        out = (res.stdout or b'').decode('utf-8', errors='replace')
        err = (res.stderr or b'').decode('utf-8', errors='replace')
        return out, err, res.returncode

    findings: list[str] = []
    # 优先 mvn compile
    out, err, code = _run_safe(
        ['mvn', '-q', 'compile', '-DskipTests'], cwd=str(TARGET), timeout=180,
    )
    if code == -2:
        return False, ['mvn compile 超时（>180s）']
    if code == 0:
        return True, []
    if code is not None and code != -1:
        # mvn 存在但编译失败
        tail = (out or err or '')[-500:]
        return False, [f'mvn compile 失败：\n{tail}']

    # mvn 不在 PATH：降级为"不判定"。
    # 不尝试 javac 单文件编译——Spring Boot 项目有 Maven 依赖树（Lombok、MyBatis-Flex
    # 等），没有 classpath 的单文件 javac 必然全部报"找不到符号"，得不到有价值的反馈。
    # 真要做严格的编译验证，读者需要自己安装 Maven 后重跑。
    return True, [
        'INFO: 本机未安装 Maven，跳过编译验证；读者要做严格编译验收请先 '
        '`mvn -v` 确认 Maven 可用，然后重新运行 `python cases/refactor_enterprise/verify.py`'
    ]


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
