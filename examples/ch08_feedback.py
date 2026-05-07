"""
第 8 章 反馈调节最小演示
========================
Ch8 完整反馈闭环涉及 Eval 框架、失败挖掘、Shadow Testing、Red Team 等，
体量较大。本脚本聚焦最简单的入门示例：**从一个 session.jsonl 中挖掘失败模式**。

流程：
    1. 加载 session.jsonl（一行一个 turn 记录）
    2. 抽取所有"工具调用 → 错误返回"的 pattern
    3. 按 (tool_name, error_class) 聚合排序
    4. 输出 Top-K 失败模式 → 这是 Ch8 8.5 节"半自动生成 CLAUDE.md 规则"的输入

用法:
    python examples/ch08_feedback.py                      # 使用内置示例数据
    python examples/ch08_feedback.py session.jsonl        # 分析指定会话
    python examples/ch08_feedback.py session.jsonl --top 20

更完整的失败挖掘 / Shadow / Red Team 实现见 experiments/ch08/*。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "ch08"))
from feedback_loop import mine_failures as _mine_failure_rows  # noqa: E402

# --- 内置示例数据（如果没有传 jsonl 文件就用这份） ---
SAMPLE_TURNS = [
    {"role": "tool", "tool_name": "bash", "ok": False,
     "error": "FileNotFoundError: bash"},
    {"role": "tool", "tool_name": "edit_file", "ok": False,
     "error": "ValueError: old_string not found in file"},
    {"role": "tool", "tool_name": "edit_file", "ok": False,
     "error": "ValueError: old_string not found in file"},
    {"role": "tool", "tool_name": "bash", "ok": False,
     "error": "TimeoutError: command exceeded 30s"},
    {"role": "tool", "tool_name": "edit_file", "ok": True},
    {"role": "tool", "tool_name": "read_file", "ok": False,
     "error": "PermissionError: .env"},
    {"role": "tool", "tool_name": "edit_file", "ok": False,
     "error": "ValueError: old_string not found in file"},
]


def load_session(path: Path | None) -> list[dict]:
    if path is None:
        return SAMPLE_TURNS
    turns: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return turns


_ERROR_CLASS_PATTERNS = [
    (re.compile(r"FileNotFoundError"), "FileNotFound"),
    (re.compile(r"PermissionError"), "Permission"),
    (re.compile(r"TimeoutError|exceeded \d+s"), "Timeout"),
    (re.compile(r"old_string not found"), "EditNotFound"),
    (re.compile(r"ValueError"), "ValueError"),
    (re.compile(r"\b400\b|context.*overflow"), "ContextOverflow"),
]


def classify(err: str) -> str:
    for pat, label in _ERROR_CLASS_PATTERNS:
        if pat.search(err):
            return label
    return "Other"


def mine_failures(turns: list[dict]) -> Counter:
    """返回 Counter[(tool_name, error_class)] -> count。"""
    return Counter({
        (row["tool"], row["error_class"]): row["count"]
        for row in _mine_failure_rows(turns)
    })


def main(argv: list[str]) -> int:
    path: Path | None = None
    top = 10
    args = list(argv[1:])
    while args:
        a = args.pop(0)
        if a == "--top":
            top = int(args.pop(0))
        else:
            path = Path(a)

    turns = load_session(path)
    print(f"加载 {len(turns)} 个 turn（来源：{path or '内置示例'}）")
    bag = mine_failures(turns)
    if not bag:
        print("未发现失败 pattern。")
        return 0

    print(f"\nTop {top} 失败模式（tool, error_class → 次数）：\n")
    for (tool, cls), n in bag.most_common(top):
        print(f"  {n:>4}  {tool:<14} {cls}")

    print("\n下一步：把高频失败转化为 CLAUDE.md 规则候选。")
    print("详见 experiments/ch08/exp2_failure_mining/。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
