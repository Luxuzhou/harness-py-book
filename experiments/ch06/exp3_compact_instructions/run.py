"""
实验三：Compact Instructions 对任务目标保持的效果
====================================================
对应书稿 6.6.3。

设计（受控对照）：
  自变量：CLAUDE.md 的 Compact Instructions 段落形态（三变体）
    - without:         CLAUDE.md 不含 Compact Instructions 段落
    - with:            朴素"保留所有步骤（包括未完成的）"写法
    - with_structured: 结构化"用 [x]/[ ] 标记每个步骤完成状态"写法
  确定性干预：在第 4 轮 LLM 调用前强制触发一次 Level 2 Compaction
             （via AgentConfig.force_compact_at_turns=(4,)，0.70 阈值保持现实值，
              避免被动触发带来的时机噪声）
  因变量：
    - 摘要内容：是否提到"剩余步骤"、是否覆盖后段任务词
    - 行为：压缩后 Agent 是否继续到自然停止、pytest 通过数
    - 结构：摘要字符数、压缩前后 token 对比

样本：
  --smoke: three variants × {42, 7} = 6 次
  full:    three variants × 10 seeds = 30 次

用法：
    python run.py --smoke
    python run.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, str(_REPO_ROOT))

# 隔离 CLAUDE.md 发现（避免受仓库根的 CLAUDE.md 污染）
import harness_py.prompt as _prompt_mod  # noqa: E402


def _isolated_discover(cwd):
    cwd = Path(cwd) if not isinstance(cwd, Path) else cwd
    claude = cwd.resolve() / 'CLAUDE.md'
    if claude.exists():
        try:
            return [(Path('CLAUDE.md'), claude.read_text(encoding='utf-8'))]
        except Exception:
            return []
    return []


_prompt_mod.discover_claude_md = _isolated_discover

from harness_py.agent import run  # noqa: E402
from harness_py.config import AgentConfig, ModelConfig  # noqa: E402

EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures'
WORKDIR = EXP_DIR / '_workdir'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)

VARIANT_FILES = {
    'with': FIXTURES / 'claude_md_variants' / 'with_compact_instructions.md',
    'without': FIXTURES / 'claude_md_variants' / 'without.md',
    'with_structured': FIXTURES / 'claude_md_variants' / 'with_structured_compact.md',
}

# 干预点：在第 4 轮 LLM 调用开始前强制压缩一次
INJECT_TURN = 4
MAX_ITERATIONS = 20  # 压缩后留 16 轮恢复预算

# 摘要质量检测的关键词集（宽松信号，基本 100% 匹配，保留为兼容性字段）
REMAINING_KEYWORDS = ('remaining', 'remain', '未完成', '还未', '还需', '剩余',
                      'in progress', 'next step', 'to do', 'todo',
                      '步骤 4', '步骤 5', 'step 4', 'step 5')
LATE_STEP_KEYWORDS = ('readme', 'shutdown', 'cost tracking', 'print',
                      'json.dumps', 'summary(', '## cost')

# 更锋利的结构化度量：是否产出"正规步骤清单"
# Compact Instructions 的真实效果是让摘要出现形如 `[Remaining Steps]`、
# `## 步骤清单`、或跨行 `1. **...**  2. **...**` 的正式步骤枚举段落。
# without 变体在相同 system prompt hierarchy 下倾向产出单行表格或内联列表，
# 不会出现这些结构。
_STEP_LIST_PATTERNS = (
    re.compile(r'\[remaining steps\]', re.I),
    re.compile(r'remaining steps', re.I),
    re.compile(r'步骤清单'),
    re.compile(r'剩余步骤'),
    re.compile(r'未完成步骤'),
    re.compile(r'##+\s*步骤'),
    re.compile(r'##+\s*remaining', re.I),
    # 跨行的正式编号项（2 条及以上、各占一行）
    re.compile(r'(?m)^\s*1[.\)]\s.*\n(?:.*\n)?\s*2[.\)]\s'),
)
# markdown 多级标题计数：反映摘要的"结构化深度"
_HEADING_PATTERN = re.compile(r'(?m)^\s*#{1,6}\s+\S')


def _detect_step_list(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _STEP_LIST_PATTERNS)


def _count_headings(text: str) -> int:
    if not text:
        return 0
    return len(_HEADING_PATTERN.findall(text))


@dataclass
class TrialResult:
    variant: str
    seed: int
    # 最终任务结果
    pytest_passed: int
    pytest_total: int
    all_pass: bool
    # Agent 行为
    turns: int
    tool_calls: int
    stop_reason: str
    # 压缩事件
    compact_triggered: bool
    compact_events_count: int
    forced_compact_occurred: bool
    pre_tokens: int               # 强制压缩前 tokens
    post_tokens: int              # 强制压缩后 tokens
    compact_summary_chars: int
    summary_mentions_remaining: bool
    summary_mentions_late_steps: bool
    # 结构化度量——区分 with / without 的真正锋利指标
    summary_has_step_list: bool   # 是否含正式步骤清单段落
    summary_heading_count: int    # markdown heading 行数（结构化深度）
    summary_text_preview: str     # 摘要前 400 字符，便于章节引用
    wall_seconds: float


def prepare_workdir(variant: str, seed: int) -> Path:
    """为一次 trial 准备独立工作目录。"""
    wd = WORKDIR / f'{variant}_seed{seed}'
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    for f in FIXTURES.iterdir():
        if f.is_file():
            shutil.copy(f, wd / f.name)
    shutil.copy(VARIANT_FILES[variant], wd / 'CLAUDE.md')
    return wd


def count_pytest_passes(workdir: Path) -> tuple[int, int]:
    """独立验证：跑 pytest，返回 (passed, total)。"""
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'test_expected.py',
             '--tb=no', '-q'],
            cwd=workdir, capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return (0, 5)
    output = proc.stdout + proc.stderr
    passed = 0
    for line in output.splitlines():
        line = line.strip()
        if 'passed' in line or 'failed' in line:
            parts = line.replace('=', ' ').split()
            for i, p in enumerate(parts):
                if p.isdigit() and i + 1 < len(parts):
                    if parts[i + 1].startswith('passed'):
                        passed = int(p)
    return (passed, 5)


def _analyze_summary(text: str) -> dict:
    """返回所有摘要度量的字典，便于扩展。"""
    if not text:
        return {
            'mentions_remaining': False,
            'mentions_late': False,
            'has_step_list': False,
            'heading_count': 0,
        }
    low = text.lower()
    return {
        'mentions_remaining': any(kw.lower() in low for kw in REMAINING_KEYWORDS),
        'mentions_late': any(kw.lower() in low for kw in LATE_STEP_KEYWORDS),
        'has_step_list': _detect_step_list(text),
        'heading_count': _count_headings(text),
    }


def run_trial(variant: str, seed: int) -> TrialResult:
    wd = prepare_workdir(variant, seed)
    task = (FIXTURES / 'task_description.md').read_text(encoding='utf-8')

    mc = ModelConfig.from_env()
    mc.temperature = 0.1 + (seed % 10) * 0.01  # 轻微方差

    ac = AgentConfig(
        cwd=wd,
        max_iterations=MAX_ITERATIONS,
        planning_turns=2,
        allow_shell=True,
        allow_destructive=False,
        compress_threshold_pct=0.70,           # 现实阈值
        # 强制 Compact 时需要有可压缩的候选消息：
        # 第 4 轮之前最少 8 条消息，preserve*2 = tail 大小必须 <7 才有候选。
        # preserve=2 → tail=4，留 3+ 条候选，_compact 能拿到实质内容。
        compact_preserve_messages=2,
        force_compact_at_turns=(INJECT_TURN,),  # 确定性干预
    )

    t0 = time.time()
    try:
        result = run(task, model_config=mc, agent_config=ac)
    except Exception as exc:
        return TrialResult(
            variant=variant, seed=seed,
            pytest_passed=0, pytest_total=5, all_pass=False,
            turns=0, tool_calls=0, stop_reason=f'exception: {exc}',
            compact_triggered=False, compact_events_count=0,
            forced_compact_occurred=False,
            pre_tokens=0, post_tokens=0,
            compact_summary_chars=0,
            summary_mentions_remaining=False,
            summary_mentions_late_steps=False,
            summary_has_step_list=False,
            summary_heading_count=0,
            summary_text_preview='',
            wall_seconds=time.time() - t0,
        )

    wall = time.time() - t0

    # 从 result.compact_events 提取观测
    events = result.compact_events
    forced = [e for e in events if e.get('forced')]
    forced_event = forced[0] if forced else None

    summary_text = forced_event.get('summary_text', '') if forced_event else ''
    analysis = _analyze_summary(summary_text)

    passed, total = count_pytest_passes(wd)

    return TrialResult(
        variant=variant, seed=seed,
        pytest_passed=passed, pytest_total=total,
        all_pass=(passed == total and total > 0),
        turns=result.turns, tool_calls=result.tool_calls,
        stop_reason=result.stop_reason or 'ok',
        compact_triggered=bool(events),
        compact_events_count=len(events),
        forced_compact_occurred=bool(forced_event),
        pre_tokens=forced_event.get('pre_tokens', 0) if forced_event else 0,
        post_tokens=forced_event.get('post_tokens', 0) if forced_event else 0,
        compact_summary_chars=len(summary_text),
        summary_mentions_remaining=analysis['mentions_remaining'],
        summary_mentions_late_steps=analysis['mentions_late'],
        summary_has_step_list=analysis['has_step_list'],
        summary_heading_count=analysis['heading_count'],
        summary_text_preview=summary_text[:400],
        wall_seconds=wall,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--seeds', type=int, nargs='+', default=None)
    ap.add_argument('--variants', nargs='+',
                    choices=list(VARIANT_FILES.keys()),
                    default=None,
                    help='只跑指定变体（默认跑 with 和 without）。指定 --variants 时使用 append 模式')
    args = ap.parse_args()

    if args.smoke:
        seeds = args.seeds or [42, 7]
    else:
        seeds = args.seeds or [42, 7, 123, 2024, 99, 11, 33, 77, 88, 101]

    # --variants 指定时 append 到现有 raw.jsonl；未指定时默认只跑 with/without 覆盖写
    if args.variants:
        variants = args.variants
        mode = 'a'
    else:
        variants = ['with', 'without']
        mode = 'w'

    out = RESULTS / 'raw.jsonl'
    idx = 0
    total = len(seeds) * len(variants)
    with out.open(mode, encoding='utf-8') as f:
        for variant in variants:
            for seed in seeds:
                idx += 1
                print(f'[{idx}/{total}] variant={variant} seed={seed}')
                r = run_trial(variant, seed)
                print(f'    forced={r.forced_compact_occurred} '
                      f'chars={r.compact_summary_chars} '
                      f'step_list={r.summary_has_step_list} '
                      f'headings={r.summary_heading_count} '
                      f'pass={r.pytest_passed}/{r.pytest_total}')
                f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')
                f.flush()

    print(f'\n原始数据已写入 {out}（mode={mode}）')


if __name__ == '__main__':
    main()
