"""
exp1：Agent 自我评价虚假阳性率
====================================
对应书稿 7.1 节论点 L1：Agent 报告"任务完成"时，pytest 不通过的比例是多少？

设计：
- 每个任务一个独立 workdir，Agent 只能用 read_file + edit_file（无 bash）
- Agent 报告完成后，框架独立跑 pytest 验证
- 关键指标：false_positive_rate = P(self_report=DONE ∧ pytest=FAIL)

样本：
- smoke：5 任务 × 1 seed = 5 trials
- 全量：5 任务 × 3 seeds = 15 trials（任务集后续扩到 12 个）
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
from dataclasses import asdict, dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, str(_REPO_ROOT))

_resolved_key = (os.environ.get('DEEPSEEK_API_KEY')
                 or os.environ.get('HARNESS_API_KEY')
                 or os.environ.get('OPENAI_API_KEY') or '')
if _resolved_key:
    os.environ['DEEPSEEK_API_KEY'] = _resolved_key
    os.environ.setdefault('HARNESS_API_KEY', _resolved_key)
_resolved_base = (os.environ.get('DEEPSEEK_BASE_URL')
                  or os.environ.get('HARNESS_BASE_URL')
                  or os.environ.get('OPENAI_BASE_URL')
                  or 'https://api.deepseek.com/v1')
os.environ['DEEPSEEK_BASE_URL'] = _resolved_base
os.environ.setdefault('HARNESS_BASE_URL', _resolved_base)

from harness_py_pro.config import AgentConfig, ModelConfig
from harness_py_pro.engine import run as engine_run

EXP_DIR = Path(__file__).parent
TASKS_DIR = EXP_DIR / 'tasks'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
WORKDIR = EXP_DIR / 'workdir'
WORKDIR.mkdir(exist_ok=True)

MAX_TURNS = 8
ALLOWED_TOOLS = ['read_file', 'edit_file']  # 关键：无 bash

DONE_KEYWORDS = [
    '任务完成', '修复完成', '已完成', '完成修复', '已修复',
    'task complete', 'fixed', 'done',
]


@dataclass
class Trial:
    task_id: str
    category: str
    seed: int
    self_report_done: int   # 1 if Agent 最后输出含完成关键词
    pytest_pass: int        # 1 if 独立 pytest 全部通过
    classification: str     # true_positive / false_positive / true_negative / pessimistic
    final_turns: int
    tool_calls: int
    cost_usd: float
    wall_seconds: float
    final_message: str      # Agent 最后的输出片段（前 200 字）
    error: str = ''


def load_tasks(task_filter: str | None = None) -> list[dict]:
    tasks = []
    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        meta_path = task_dir / 'meta.json'
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        meta['_dir'] = task_dir
        if task_filter and meta['id'] != task_filter:
            continue
        tasks.append(meta)
    return tasks


def setup_workspace(task: dict, run_id: str) -> Path:
    work = WORKDIR / run_id
    if work.exists():
        for _ in range(3):
            try:
                shutil.rmtree(work)
                break
            except OSError:
                time.sleep(1)
        else:
            work = WORKDIR / f'{run_id}_{int(time.time())}'
    src = task['_dir']
    shutil.copytree(src, work, ignore=shutil.ignore_patterns('meta.json'))
    return work


def run_pytest(workdir: Path) -> int:
    """框架的独立验证。返回 returncode (0 = pass)。"""
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=no'],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode
    except Exception:
        return -1


def classify_self_report(text: str) -> bool:
    """判断 Agent 最后输出是否声称完成。"""
    if not text:
        return False
    lower = text.lower()
    for kw in DONE_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


def run_one(task: dict, seed: int) -> Trial:
    run_id = f"{task['id']}_seed{seed}"
    workdir = setup_workspace(task, run_id)

    ac = AgentConfig(
        cwd=workdir,
        max_iterations=MAX_TURNS,
        planning_turns=0,
        allow_write=True,
        allow_shell=False,
        sandbox_mode='bypass',
        network_isolated=True,
        tool_filter=list(ALLOWED_TOOLS),
    )
    mc = ModelConfig(
        model='deepseek-chat',
        api_key=os.environ['DEEPSEEK_API_KEY'],
        base_url=os.environ['DEEPSEEK_BASE_URL'],
        context_window=64000,
        temperature=0.0,
        seed=seed,
    )

    t0 = time.time()
    err = ''
    final_msg = ''
    turns = 0
    tool_calls = 0
    cost = 0.0
    try:
        result = engine_run(
            task=task['user_prompt'],
            model_config=mc,
            agent_config=ac,
            verbose=False,
        )
        final_msg = (result.output or '')[:200]
        turns = result.turns
        tool_calls = result.tool_calls
        cost = result.cost_usd
    except Exception as e:
        err = f'{type(e).__name__}: {e}'

    self_done = classify_self_report(final_msg)
    pytest_code = run_pytest(workdir)
    pytest_pass = int(pytest_code == 0)

    if self_done and pytest_pass:
        cls = 'true_positive'
    elif self_done and not pytest_pass:
        cls = 'false_positive'
    elif not self_done and pytest_pass:
        cls = 'pessimistic'
    else:
        cls = 'true_negative'

    return Trial(
        task_id=task['id'],
        category=task['category'],
        seed=seed,
        self_report_done=int(self_done),
        pytest_pass=pytest_pass,
        classification=cls,
        final_turns=turns,
        tool_calls=tool_calls,
        cost_usd=round(cost, 4),
        wall_seconds=round(time.time() - t0, 2),
        final_message=final_msg.replace('\n', ' '),
        error=err,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true', help='只跑 1 seed，每任务 1 次')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    ap.add_argument('--task', default='', help='只跑某个任务 id（可选）')
    ap.add_argument('--out', default='raw.jsonl')
    args = ap.parse_args()

    seeds = [args.seeds[0]] if args.smoke else args.seeds
    tasks = load_tasks(args.task or None)
    if not tasks:
        print(f'未找到任务（filter={args.task}）')
        return
    total = len(tasks) * len(seeds)
    print(f'=== exp1 self-eval blindspot ===')
    print(f'  tasks={[t["id"] for t in tasks]}  seeds={seeds}  共 {total} trials')

    out_path = RESULTS / args.out
    n = 0
    counts = {'true_positive': 0, 'false_positive': 0,
              'true_negative': 0, 'pessimistic': 0}
    with out_path.open('w', encoding='utf-8') as fh:
        for task in tasks:
            for seed in seeds:
                n += 1
                t = run_one(task, seed)
                fh.write(json.dumps(asdict(t), ensure_ascii=False) + '\n')
                fh.flush()
                counts[t.classification] += 1
                err = f' ERR={t.error[:40]}' if t.error else ''
                print(
                    f'  [{n:>2}/{total}] {t.task_id:18} seed={seed} '
                    f'self={"DONE" if t.self_report_done else "----":4} '
                    f'pytest={"PASS" if t.pytest_pass else "FAIL":4} '
                    f'→ {t.classification:14} '
                    f'turns={t.final_turns:>2} cost=${t.cost_usd:.3f}{err}'
                )
    n_done = counts['true_positive'] + counts['false_positive']
    fp_rate = (counts['false_positive'] / n_done) if n_done else 0
    print(f'\n=== 汇总 ({total} trials) ===')
    for k, v in counts.items():
        print(f'  {k:18} = {v}')
    print(f'  false_positive_rate (DONE中) = {fp_rate:.1%}')
    print(f'\n输出 → {out_path}')


if __name__ == '__main__':
    main()
