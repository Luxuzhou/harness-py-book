"""
实验四：Dream 整理的量化效果
===============================
对应书稿 6.4.3。

对 10 份样例 Memory 文件跑 Dream 的规则式整理，测量行数变化、重复去除、
相对日期转换等指标。无 LLM API 调用，无需 key。

用法：
    python run.py
    python run.py --file duplicate_heavy.md   # 单文件模式（调试用）

首次运行前若 fixtures/ 为空，需要执行：
    python generate_fixtures.py
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures'
RESULTS = EXP_DIR / 'results'
DIFFS = RESULTS / 'diffs'
RESULTS.mkdir(exist_ok=True)
DIFFS.mkdir(exist_ok=True)

# 固定"今天"的日期，保证可复现
FIXED_TODAY = '2026-04-19'
FIXED_YESTERDAY = '2026-04-18'
MAX_LINES = 200


@dataclass
class DreamResult:
    file: str
    lines_before: int
    lines_after: int
    reduction_pct: float
    duplicates_removed: int
    relative_dates_converted: int
    pruned_empty: bool
    bytes_before: int
    bytes_after: int


def _split_frontmatter(text: str) -> tuple[str, str]:
    """分离 YAML front matter。返回 (fm, body)；fm 含首尾 ``---``，无 front matter 时 fm 为空。"""
    m = re.match(r'^(---\n.*?\n---\n?)(.*)', text, flags=re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    return '', text


def consolidate(text: str) -> tuple[str, dict]:
    """规则式整理，对齐书稿 6.4.3 的伪代码。返回 (整理后文本, 统计)。

    保护 YAML front matter：只对正文 body 做日期转换、去重、裁剪，front matter 原样保留。
    front matter 中的 ``---`` 边界不会被去重误删，duplicates 也不统计 YAML 的分隔符。
    """
    stats = {'duplicates': 0, 'dates': 0}
    fm, body = _split_frontmatter(text)

    # Step 1: 日期转换（只作用于 body）
    for token, repl in [
        ('今天', FIXED_TODAY), ('today', FIXED_TODAY),
        ('昨天', FIXED_YESTERDAY), ('yesterday', FIXED_YESTERDAY),
    ]:
        count = len(re.findall(token, body, flags=re.IGNORECASE))
        if count:
            body = re.sub(token, repl, body, flags=re.IGNORECASE)
            stats['dates'] += count

    # Step 2: 行级去重（只作用于 body，大小写不敏感）
    lines = body.splitlines()
    seen: set[str] = set()
    deduped: list[str] = []
    for line in lines:
        norm = line.strip().lower()
        if norm and norm in seen:
            stats['duplicates'] += 1
            continue
        if norm:
            seen.add(norm)
        deduped.append(line)

    # Step 3: 裁剪到 MAX_LINES（作用于 body 行数）
    if len(deduped) > MAX_LINES:
        deduped = deduped[:MAX_LINES]

    return fm + '\n'.join(deduped), stats


def content_is_empty(text: str) -> bool:
    """去除 YAML front matter 后是否只剩空行。"""
    body = re.sub(r'^---.*?---\s*', '', text, count=1, flags=re.DOTALL)
    stripped = [line for line in body.splitlines() if line.strip() and not line.strip().startswith('#')]
    return len(stripped) == 0


def process(path: Path) -> tuple[DreamResult, str, str]:
    """返回 (度量, 整理前文本, 整理后文本)。"""
    before = path.read_text(encoding='utf-8')
    after, stats = consolidate(before)
    pruned = content_is_empty(after)
    lines_before = len(before.splitlines())
    lines_after = len(after.splitlines())
    reduction = round((1 - lines_after / lines_before) * 100, 1) if lines_before else 0.0
    return DreamResult(
        file=path.name,
        lines_before=lines_before,
        lines_after=lines_after,
        reduction_pct=reduction,
        duplicates_removed=stats['duplicates'],
        relative_dates_converted=stats['dates'],
        pruned_empty=pruned,
        bytes_before=len(before.encode('utf-8')),
        bytes_after=len(after.encode('utf-8')),
    ), before, after


def write_diff(result: DreamResult, before: str, after: str):
    path = DIFFS / f'{result.file}.md'
    content = [
        f'# Dream 整理前后对比：{result.file}',
        '',
        f'- 行数：{result.lines_before} → {result.lines_after} （'
        f'降 {result.reduction_pct}%）',
        f'- 重复去除：{result.duplicates_removed}',
        f'- 相对日期转换：{result.relative_dates_converted}',
        f'- 空文件：{"是" if result.pruned_empty else "否"}',
        '',
        '## Before', '', '```', before, '```',
        '',
        '## After', '', '```', after, '```',
    ]
    path.write_text('\n'.join(content), encoding='utf-8')


def write_summary(results: list[DreamResult]):
    raw = RESULTS / 'raw.jsonl'
    with raw.open('w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')

    csv_path = RESULTS / 'summary.csv'
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))

    # 终端打印总结
    total_before = sum(r.lines_before for r in results)
    total_after = sum(r.lines_after for r in results)
    overall = round((1 - total_after / total_before) * 100, 1) if total_before else 0.0
    print(f'\n=== Dream 整理总结（n={len(results)}） ===')
    print(f'总行数：{total_before} → {total_after}（降 {overall}%）')
    print(f'重复去除总数：{sum(r.duplicates_removed for r in results)}')
    print(f'相对日期转换总数：{sum(r.relative_dates_converted for r in results)}')
    print(f'空文件数：{sum(1 for r in results if r.pruned_empty)}')
    print(f'\n详细对比见 {DIFFS}')
    print(f'raw JSONL：{raw}')
    print(f'summary CSV：{csv_path}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', help='只跑单份文件（调试用）')
    args = ap.parse_args()

    files = list(FIXTURES.glob('*.md'))
    if args.file:
        files = [f for f in files if f.name == args.file]
    if not files:
        print(f'ERROR: 无 fixture 文件。请先 `python generate_fixtures.py`。')
        return

    results = []
    for path in sorted(files):
        print(f'processing {path.name}...')
        r, before, after = process(path)
        write_diff(r, before, after)
        results.append(r)

    write_summary(results)


if __name__ == '__main__':
    main()
