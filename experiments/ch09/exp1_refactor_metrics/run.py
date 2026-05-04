"""
重构前后量化对照（采样器）
============================
对应书稿 9.5。在 cases/refactor_enterprise/target_project/ 上算 5 个指标。

用法：
    python run.py before   # 当前 tree 算一次，写 results/before.json
    python run.py after    # 同上，写 results/after.json
    python compare.py      # 生成 markdown 对照表
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

EXP_DIR = Path(__file__).parent
REPO_ROOT = EXP_DIR.parents[2]
TARGET = REPO_ROOT / 'cases' / 'refactor_enterprise' / 'target_project'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)


@dataclass
class Metrics:
    snapshot_label: str
    java_file_count: int
    total_loc: int
    god_service_loc: int            # CpPlanService.java 的行数
    avg_method_loc: float           # 估算的平均方法长度
    pmd_warnings: int               # 0 表示未跑 PMD
    test_line_coverage: float       # -1.0 表示未跑覆盖率


def _which(cmd: str) -> bool:
    try:
        subprocess.run([cmd, '--version'], capture_output=True, check=False, timeout=5)
        return True
    except FileNotFoundError:
        return False


def count_java_files(target: Path) -> int:
    return sum(1 for _ in target.rglob('*.java'))


def total_loc(target: Path) -> int:
    """所有 .java 文件总行数。"""
    n = 0
    for f in target.rglob('*.java'):
        try:
            n += sum(1 for _ in f.open(encoding='utf-8', errors='ignore'))
        except Exception:
            continue
    return n


def god_service_loc(target: Path) -> int:
    """CpPlanService.java 的行数（章节里的 God Service）。"""
    candidates = list(target.rglob('CpPlanService.java'))
    if not candidates:
        return 0
    return sum(1 for _ in candidates[0].open(encoding='utf-8', errors='ignore'))


def avg_method_loc(target: Path) -> float:
    """估算平均方法长度：'public/private/protected ... {' 之间的行数中位数的平均。"""
    # 简化估算：扫描所有 .java，识别 method opening brace，计算到下一个 brace 的距离
    method_lengths: list[int] = []
    method_pat = re.compile(r'\b(public|private|protected)\s+[\w<>,\s]+\s+\w+\s*\([^)]*\)\s*\{')
    for f in target.rglob('*.java'):
        try:
            text = f.read_text(encoding='utf-8', errors='ignore')
            lines = text.split('\n')
            in_method = False
            depth = 0
            cur_len = 0
            for line in lines:
                if not in_method:
                    if method_pat.search(line):
                        in_method = True
                        depth = line.count('{') - line.count('}')
                        cur_len = 1
                else:
                    cur_len += 1
                    depth += line.count('{') - line.count('}')
                    if depth <= 0:
                        method_lengths.append(cur_len)
                        in_method = False
        except Exception:
            continue
    return round(sum(method_lengths) / len(method_lengths), 2) if method_lengths else 0.0


def pmd_warnings(target: Path) -> int:
    """如果 PMD 可用，跑一次基础规则集；否则返回 0 表示未测。"""
    if not _which('pmd'):
        return 0
    try:
        proc = subprocess.run(
            ['pmd', 'check', '-d', str(target), '-R', 'rulesets/java/quickstart.xml',
             '-f', 'text'],
            capture_output=True, text=True, timeout=120,
        )
        return len([line for line in proc.stdout.splitlines() if ':' in line and '.java' in line])
    except Exception:
        return 0


def test_line_coverage(target: Path) -> float:
    """如果 mvn + jacoco 可用，跑测试取 line 覆盖率；否则返回 -1.0。"""
    pom = target / 'pom.xml'
    if not pom.exists() or not _which('mvn'):
        return -1.0
    # 简化：假设 jacoco-maven-plugin 已配置，用户可手动跑 mvn test 后由 compare.py 解析报告
    return -1.0


def collect(label: str) -> Metrics:
    if not TARGET.exists():
        raise FileNotFoundError(f"目标项目不存在：{TARGET}")
    print(f"采集 {label} metrics 自 {TARGET} ...")
    return Metrics(
        snapshot_label=label,
        java_file_count=count_java_files(TARGET),
        total_loc=total_loc(TARGET),
        god_service_loc=god_service_loc(TARGET),
        avg_method_loc=avg_method_loc(TARGET),
        pmd_warnings=pmd_warnings(TARGET),
        test_line_coverage=test_line_coverage(TARGET),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('label', choices=['before', 'after'], help='当前 tree 是重构前还是后')
    args = ap.parse_args()

    m = collect(args.label)
    out = RESULTS / f'{args.label}.json'
    out.write_text(json.dumps(asdict(m), indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"\n=== {args.label.upper()} 快照 ===")
    for k, v in asdict(m).items():
        print(f"  {k:25} {v}")
    print(f"\n写入 {out}")


if __name__ == '__main__':
    main()
