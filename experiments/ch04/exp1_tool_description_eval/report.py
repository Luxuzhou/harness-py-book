"""
report.py
==========
将 eval_runner.py 输出的 results_*.json 聚合为 Markdown 报告。

支持两种模式：
  - 单文件：生成某一个版本的完整详细报告
  - 双文件：生成 v1 vs v2 对比报告（推荐）

用法:
    python report.py results_v1.json
    python report.py results_v1.json results_v2.json > comparison.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Windows 下 print 到文件默认 GBK，会丢中文。强制 UTF-8。
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    # 懒更新：从 all_calls 补算 any_call_right，支持旧JSON
    for r in data['results']:
        r['any_call_right'] = _compute_any_call_right(r)
    return data


def _compute_any_call_right(r: dict) -> bool:
    """
    any_call_right: expected_tool 是否出现在 all_calls 的任意一次调用中。
    对 expected_tool=None 的negative case，等价于 no calls were made。

    这个指标承认"Agent先探索再动作"是正确工作流，
    而 first_call_right（即原 selected_right）要求首call就命中。
    """
    expected = r.get('expected_tool')
    all_calls = r.get('all_calls', [])
    if expected is None:
        return len(all_calls) == 0
    return any(c.get('name') == expected for c in all_calls)


def by_category(results: list[dict]) -> dict:
    """按 category 聚合指标（双轨：first_call + any_call）。"""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        buckets[r.get('category', '(unknown)')].append(r)

    agg = {}
    for cat, rs in buckets.items():
        n = len(rs)
        agg[cat] = {
            'n': n,
            'first_call_accuracy': sum(1 for r in rs if r['selected_right']) / n,
            'any_call_accuracy': sum(1 for r in rs if r['any_call_right']) / n,
            'forbidden_hit_rate': sum(1 for r in rs if r['forbidden_hit']) / n,
            'args_correctness': sum(1 for r in rs if r['args_ok']) / n,
        }
    return agg


def confusion_top(results: list[dict], top_n: int = 10) -> list[tuple]:
    """统计最常见的"期望X但选Y"混淆模式。"""
    confusion: Counter = Counter()
    for r in results:
        if r['selected_right']:
            continue
        expected = r.get('expected_tool') or '<no_call>'
        got = r['first_call']['name'] if r['first_call'] else '<no_call>'
        confusion[(expected, got)] += 1
    return confusion.most_common(top_n)


def fmt_pct(v: float) -> str:
    return f'{v*100:.1f}%'


def print_single(report_data: dict):
    """单版本详细报告（双轨：first_call + any_call）。"""
    summary = report_data['summary']
    results = report_data['results']
    version = summary['version']

    n = len(results)
    first_call_acc = sum(1 for r in results if r['selected_right']) / n
    any_call_acc = sum(1 for r in results if r['any_call_right']) / n

    print(f'# Tool Description Eval Report — `{version}`\n')
    print('## 1. 总览（双轨指标）\n')
    print('| 指标 | 值 | 含义 |')
    print('|------|------|------|')
    print(f'| 任务数 | {summary["num_cases"]} | |')
    print(f'| Seeds | {summary["seeds"]} | |')
    print(f'| 总观测数 | {n} | |')
    print(f'| **First-call Accuracy** | **{fmt_pct(first_call_acc)}** | 首次tool call即命中（描述质量） |')
    print(f'| **Any-call Accuracy** | **{fmt_pct(any_call_acc)}** | 多轮内命中（Agent能力+描述，含recovery） |')
    print(f'| Forbidden Hit Rate | {fmt_pct(summary["forbidden_hit_rate"])} | 首次即误调禁用工具 |')
    print(f'| Args Correctness | {fmt_pct(summary["args_correctness"])} | 参数语义正确 |')
    print(f'| Error Rate | {fmt_pct(summary["error_rate"])} | |')
    print()

    print('## 2. 按 Category 拆解（双轨）\n')
    print('| Category | N | First-call | Any-call | Forbidden | Args |')
    print('|----------|---|-----------|----------|-----------|------|')
    cats = by_category(results)
    for cat in sorted(cats.keys()):
        m = cats[cat]
        print(
            f'| `{cat}` | {m["n"]} | {fmt_pct(m["first_call_accuracy"])} '
            f'| {fmt_pct(m["any_call_accuracy"])} '
            f'| {fmt_pct(m["forbidden_hit_rate"])} '
            f'| {fmt_pct(m["args_correctness"])} |'
        )
    print()

    print('## 3. 混淆模式 Top 10\n')
    print('| 期望 | 实际选择 | 次数 |')
    print('|------|----------|------|')
    for (exp, got), cnt in confusion_top(results):
        print(f'| `{exp}` | `{got}` | {cnt} |')
    print()

    print('## 4. 失败样例（前10条）\n')
    failed = [r for r in results if not r['selected_right']][:10]
    print('| ID | Seed | Want | Got | 任务 |')
    print('|----|------|------|-----|------|')
    for r in failed:
        want = r.get('expected_tool') or '<no_call>'
        got = r['first_call']['name'] if r['first_call'] else '<no_call>'
        task = _find_task_text(r['id'])
        print(f'| {r["id"]} | {r["seed"]} | {want} | {got} | {task} |')
    print()


def _overall_acc(results: list[dict], key: str) -> float:
    n = len(results)
    return sum(1 for r in results if r[key]) / n if n else 0.0


def _overall_rate(results: list[dict], key: str) -> float:
    n = len(results)
    return sum(1 for r in results if r[key]) / n if n else 0.0


def print_compare(data_v1: dict, data_v2: dict):
    """v1 vs v2 对比报告（双轨）。"""
    r1 = data_v1['results']
    r2 = data_v2['results']

    print('# Tool Description Eval — v1 vs v2 对比\n')
    print(f'v1 观测 = {len(r1)}, seeds = {data_v1["summary"]["seeds"]}')
    print(f'v2 观测 = {len(r2)}, seeds = {data_v2["summary"]["seeds"]}')
    print()

    print('## 1. 总体指标对比（双轨）\n')
    print('| 指标 | v1 | v2 | Δ |')
    print('|------|-----|-----|----|')
    _diff_row('First-call Accuracy (首次命中)',
              _overall_acc(r1, 'selected_right'),
              _overall_acc(r2, 'selected_right'))
    _diff_row('Any-call Accuracy (多轮命中)',
              _overall_acc(r1, 'any_call_right'),
              _overall_acc(r2, 'any_call_right'))
    _diff_row('Forbidden Hit Rate (越低越好)',
              _overall_rate(r1, 'forbidden_hit'),
              _overall_rate(r2, 'forbidden_hit'),
              invert=True)
    _diff_row('Args Correctness',
              _overall_acc(r1, 'args_ok'),
              _overall_acc(r2, 'args_ok'))
    print()

    cats_v1 = by_category(r1)
    cats_v2 = by_category(r2)
    all_cats = sorted(set(cats_v1) | set(cats_v2))

    print('## 2. 按 Category 对比 — First-call Accuracy\n')
    print('| Category | v1 | v2 | Δ |')
    print('|----------|-----|-----|----|')
    for cat in all_cats:
        a1 = cats_v1.get(cat, {}).get('first_call_accuracy', 0.0)
        a2 = cats_v2.get(cat, {}).get('first_call_accuracy', 0.0)
        delta = a2 - a1
        arrow = '+' if delta > 0 else ('-' if delta < 0 else '=')
        print(f'| `{cat}` | {fmt_pct(a1)} | {fmt_pct(a2)} | {arrow}{fmt_pct(abs(delta))} |')
    print()

    print('## 3. 按 Category 对比 — Any-call Accuracy\n')
    print('| Category | v1 | v2 | Δ |')
    print('|----------|-----|-----|----|')
    for cat in all_cats:
        a1 = cats_v1.get(cat, {}).get('any_call_accuracy', 0.0)
        a2 = cats_v2.get(cat, {}).get('any_call_accuracy', 0.0)
        delta = a2 - a1
        arrow = '+' if delta > 0 else ('-' if delta < 0 else '=')
        print(f'| `{cat}` | {fmt_pct(a1)} | {fmt_pct(a2)} | {arrow}{fmt_pct(abs(delta))} |')
    print()

    print('## 4. v2 改善最大的 Category（First-call，Top 5）\n')
    deltas = [
        (cat,
         cats_v2.get(cat, {}).get('first_call_accuracy', 0.0) -
         cats_v1.get(cat, {}).get('first_call_accuracy', 0.0))
        for cat in all_cats
    ]
    deltas.sort(key=lambda x: -x[1])
    print('| Category | v1 | v2 | 提升 |')
    print('|----------|-----|-----|------|')
    for cat, d in deltas[:5]:
        a1 = cats_v1.get(cat, {}).get('first_call_accuracy', 0.0)
        a2 = cats_v2.get(cat, {}).get('first_call_accuracy', 0.0)
        print(f'| `{cat}` | {fmt_pct(a1)} | {fmt_pct(a2)} | +{fmt_pct(d)} |')
    print()

    print('## 5. v2 退步的 Category（First-call，如有）\n')
    regressions = [(c, d) for c, d in deltas if d < -0.02]
    if not regressions:
        print('*无显著退步（所有 category 的 v2 accuracy 差值 > -2%）。*\n')
    else:
        print('| Category | v1 | v2 | 退步 |')
        print('|----------|-----|-----|------|')
        for cat, d in regressions:
            a1 = cats_v1.get(cat, {}).get('first_call_accuracy', 0.0)
            a2 = cats_v2.get(cat, {}).get('first_call_accuracy', 0.0)
            print(f'| `{cat}` | {fmt_pct(a1)} | {fmt_pct(a2)} | {fmt_pct(d)} |')
        print()

    print('## 5. 混淆模式对比\n')
    print('### v1 Top 混淆\n')
    print('| 期望 | 实际 | 次数 |')
    print('|------|------|------|')
    for (exp, got), cnt in confusion_top(r1):
        print(f'| `{exp}` | `{got}` | {cnt} |')
    print()
    print('### v2 Top 混淆\n')
    print('| 期望 | 实际 | 次数 |')
    print('|------|------|------|')
    for (exp, got), cnt in confusion_top(r2):
        print(f'| `{exp}` | `{got}` | {cnt} |')
    print()


def _diff_row(label: str, v1: float, v2: float, invert: bool = False) -> None:
    delta = v2 - v1
    good = (delta < 0) if invert else (delta > 0)
    arrow = '+' if delta > 0 else ('-' if delta < 0 else '=')
    if abs(delta) > 0.01:
        mark = ' [better]' if good else ' [worse]'
    else:
        mark = ''
    print(f'| {label} | {fmt_pct(v1)} | {fmt_pct(v2)} | {arrow}{fmt_pct(abs(delta))}{mark} |')


_GOLDEN_CACHE: dict | None = None


def _find_task_text(case_id: str) -> str:
    """从 golden_set.jsonl 查 task 原文（仅用于报告展示）。"""
    global _GOLDEN_CACHE
    if _GOLDEN_CACHE is None:
        gs = Path(__file__).parent / 'golden_set.jsonl'
        _GOLDEN_CACHE = {}
        for line in gs.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            _GOLDEN_CACHE[case['id']] = case.get('task', '')
    return _GOLDEN_CACHE.get(case_id, '')[:40]


def main():
    import io
    parser = argparse.ArgumentParser()
    parser.add_argument('files', type=Path, nargs='+',
                        help='结果 JSON 文件。传1个=详细报告，传2个=v1/v2对比')
    parser.add_argument('--out', '-o', type=Path, default=None,
                        help='写入文件（UTF-8），避免 PowerShell 用UTF-16污染')
    args = parser.parse_args()

    # 若指定 --out，把 stdout 重定向到该文件；否则正常打印到 terminal
    if args.out is not None:
        sys.stdout = io.TextIOWrapper(
            open(args.out, 'wb'), encoding='utf-8', newline='\n', write_through=True
        )

    if len(args.files) == 1:
        print_single(load(args.files[0]))
    elif len(args.files) == 2:
        d1 = load(args.files[0])
        d2 = load(args.files[1])
        if d1['summary']['version'] == 'v2' and d2['summary']['version'] == 'v1':
            d1, d2 = d2, d1
        print_compare(d1, d2)
    else:
        print('错误：只支持 1 或 2 个输入文件')

    if args.out is not None:
        sys.stdout.flush()
        sys.stdout.close()


if __name__ == '__main__':
    main()
