"""
exp5：plan-then-execute 三种实现 × 任务复杂度
=============================================
对应书稿 7.5：业界主推 plan-then-execute，但实现方式至关重要——
机械式（仅前 N 轮禁用 write）有害；文档式（强制写 plan.md）才有效。

任务分组（按 category 自动归类）：
  simple   = {add_param, change_default, add_import}            单文件 7 个任务
  complex  = {rename_call_site, cross_module_signature,
              constant_rename}                                  跨文件 5 个任务

样本量：
  smoke：1 simple + 3 complex × 3 modes × 1 seed = 12 trials
  全量：12 任务 × 3 modes × 3 seeds = 108 trials
"""
from __future__ import annotations

import argparse
import json
import os
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
TASKS_FILE = EXP_DIR / 'tasks' / 'edits.jsonl'
FIXTURES = EXP_DIR / 'fixtures'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
WORKDIR = EXP_DIR / 'workdir'
WORKDIR.mkdir(exist_ok=True)

MAX_TURNS = 15

SIMPLE_CATS = {'add_param', 'change_default', 'add_import'}
COMPLEX_CATS = {'rename_call_site', 'cross_module_signature', 'constant_rename'}

# P_doc：业界推崇的 plan-then-execute 真正实现——
# 不是机械禁用 write 工具，而是要求 Agent 把 plan 落成中间产物（plan.md）。
# 这与 Anthropic Claude Code PLAN mode、DeepAgents planner subagent、
# Cognition Devin 的设计思路一致。
PLAN_DOC_PREFIX = """在开始任何代码修改之前，你必须严格按以下两步执行。

第一步（强制）：用 write_file 工具创建 plan.md 文件，必须包含 4 个清晰段落：
  1. 现状分析：列出你读取了哪些文件，确认了什么关键事实（如函数签名、调用点位置）
  2. 修改步骤：具体要改哪些文件、改什么、按什么顺序
  3. 验证方法：怎么确认改对了（哪些 grep 模式 / 测试预期）
  4. 回滚方案：如果改坏如何恢复

第二步：基于这份 plan，开始执行实际修改。修改过程中如果发现 plan 不准确，
        必须先用 edit_file 更新 plan.md 再继续。

任务要求：
"""


def task_group(category: str) -> str:
    if category in SIMPLE_CATS:
        return 'simple'
    if category in COMPLEX_CATS:
        return 'complex'
    return 'other'


@dataclass
class Trial:
    task_id: str
    category: str
    group: str
    mode: str               # P0_none / P3_mechanical / P_doc
    planning_turns: int
    seed: int
    first_edit_success: int
    total_edits: int
    total_turns: int
    read_calls_before_edit: int
    plan_doc_written: int   # P_doc：是否真的写了 plan.md
    plan_doc_size: int      # plan.md 字符数（衡量 plan 质量）
    verify_passed: int
    cost_usd: float
    wall_seconds: float
    error: str = ''


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
    src_dir = FIXTURES / task['id']
    if not src_dir.exists():
        raise FileNotFoundError(f'fixture not found: {src_dir}')
    shutil.copytree(src_dir, work)
    return work


def parse_session(workdir: Path, session_id: str) -> dict:
    metrics = {
        'first_edit_success': 0,
        'total_edits': 0,
        'read_calls_before_edit': 0,
    }
    sf = workdir / '.harness_sessions' / f'{session_id}.jsonl'
    if not sf.exists():
        return metrics
    seen_first = False
    for line in sf.read_text(encoding='utf-8').splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get('type') != 'tool_call':
            continue
        name = ev.get('tool', '')
        ok = ev.get('ok', False)
        if name == 'edit_file':
            metrics['total_edits'] += 1
            if not seen_first:
                seen_first = True
                metrics['first_edit_success'] = int(bool(ok))
        elif name == 'read_file' and not seen_first:
            metrics['read_calls_before_edit'] += 1
    return metrics


def verify_modification(workdir: Path, task: dict) -> int:
    """优先用 pytest 验证（fixture 含 tests/）；否则回退到 grep verify_signal。

    pytest 验证比 grep 严格得多——漏改任何调用方都会让 import / 调用失败。
    grep 仅检查"某个 pattern 至少在某个 .py 中出现"，是粗糙的代理。
    """
    tests_dir = workdir / 'tests'
    has_tests = tests_dir.exists() and any(tests_dir.glob('test_*.py'))
    if has_tests:
        return _verify_via_pytest(workdir)
    return _verify_via_grep(workdir, task)


def _verify_via_pytest(workdir: Path) -> int:
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=no'],
            cwd=workdir,
            capture_output=True,
            timeout=30,
        )
        return int(proc.returncode == 0)
    except Exception:
        return 0


def _verify_via_grep(workdir: Path, task: dict) -> int:
    signal = task.get('verify_signal', '')
    if not signal:
        return 0
    patterns = [s.strip() for s in signal.split('|') if s.strip()]
    for py in workdir.rglob('*.py'):
        try:
            text = py.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for p in patterns:
            if p in text:
                return 1
    return 0


def run_one(task: dict, mode: str, seed: int) -> Trial:
    """跑一次。

    mode:
      - P0_none      : planning_turns=0, 无 plan 约束（自由发挥）
      - P3_mechanical: planning_turns=3, 前 3 轮强制只读（当前 harness_py_pro 实现）
      - P_doc        : planning_turns=0, 但 prompt 强制要求先 write_file plan.md
    """
    if mode == 'P0_none':
        planning_turns = 0
        prompt_prefix = ''
    elif mode == 'P3_mechanical':
        planning_turns = 3
        prompt_prefix = ''
    elif mode == 'P_doc':
        planning_turns = 0
        prompt_prefix = PLAN_DOC_PREFIX
    else:
        raise ValueError(f'未知 mode: {mode}')

    run_id = f"{task['id']}_{mode}_s{seed}"
    workdir = setup_workspace(task, run_id)

    user_prompt = prompt_prefix + task['user_prompt']

    ac = AgentConfig(
        cwd=workdir,
        max_iterations=MAX_TURNS,
        planning_turns=planning_turns,
        allow_write=True,
        allow_shell=False,
        sandbox_mode='bypass',
        network_isolated=True,
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
    metrics = {'first_edit_success': 0, 'total_edits': 0, 'read_calls_before_edit': 0}
    turns = 0
    cost = 0.0
    sid = ''
    try:
        result = engine_run(
            task=user_prompt,
            model_config=mc,
            agent_config=ac,
            verbose=False,
        )
        turns = result.turns
        cost = result.cost_usd
        sid = result.session_id
        metrics = parse_session(workdir, sid)
    except Exception as e:
        err = f'{type(e).__name__}: {e}'

    verified = verify_modification(workdir, task)

    plan_path = workdir / 'plan.md'
    plan_written = int(plan_path.exists())
    plan_size = len(plan_path.read_text(encoding='utf-8', errors='replace')) if plan_written else 0

    return Trial(
        task_id=task['id'],
        category=task['category'],
        group=task_group(task['category']),
        mode=mode,
        planning_turns=planning_turns,
        seed=seed,
        first_edit_success=metrics['first_edit_success'],
        total_edits=metrics['total_edits'],
        total_turns=turns,
        read_calls_before_edit=metrics['read_calls_before_edit'],
        plan_doc_written=plan_written,
        plan_doc_size=plan_size,
        verify_passed=verified,
        cost_usd=round(cost, 4),
        wall_seconds=round(time.time() - t0, 2),
        error=err,
    )


def smoke_select(tasks: list[dict]) -> list[dict]:
    """smoke 选取均衡样本：1 simple + 3 complex（rn001 + 新增 rn004 + rn005）。

    smoke 重点验证新 complex fixture 难度，所以 simple 只取 1 个看 P3 灾难是否
    复现，complex 优先 rn004/rn005 + rn001（原对照）。
    """
    chosen: list[dict] = []
    # 1 个 simple
    for t in tasks:
        if t['category'] == 'add_param':
            chosen.append(t); break
    # 3 个 complex：rn001 (原 baseline) + rn004 + rn005
    for tid in ('rn001', 'rn004', 'rn005'):
        for t in tasks:
            if t['id'] == tid:
                chosen.append(t); break
    return chosen


ALL_MODES = ['P0_none', 'P3_mechanical', 'P_doc']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    ap.add_argument('--modes', nargs='+', default=ALL_MODES)
    ap.add_argument('--out', default='raw.jsonl')
    args = ap.parse_args()

    with TASKS_FILE.open(encoding='utf-8') as fh:
        tasks = [json.loads(line) for line in fh if line.strip()]

    if args.smoke:
        tasks = smoke_select(tasks)
        seeds = [args.seeds[0]]
    else:
        seeds = args.seeds

    modes = args.modes
    total = len(tasks) * len(modes) * len(seeds)
    print(f'=== exp5 planning complexity (3-mode) ===')
    print(f'  tasks={[t["id"] for t in tasks]}')
    print(f'  modes={modes} seeds={seeds}  共 {total}')

    out_path = RESULTS / args.out
    cell_first: dict[tuple, list[int]] = {}
    cell_verify: dict[tuple, list[int]] = {}
    n = 0
    with out_path.open('w', encoding='utf-8') as fh:
        for task in tasks:
            for mode in modes:
                for seed in seeds:
                    n += 1
                    t = run_one(task, mode, seed)
                    fh.write(json.dumps(asdict(t), ensure_ascii=False) + '\n')
                    fh.flush()
                    key = (t.group, t.mode)
                    cell_first.setdefault(key, []).append(t.first_edit_success)
                    cell_verify.setdefault(key, []).append(t.verify_passed)
                    err = f' ERR={t.error[:30]}' if t.error else ''
                    print(
                        f'  [{n:>2}/{total}] {t.task_id} ({t.group:7}) {t.mode:14} '
                        f'first_edit={t.first_edit_success} '
                        f'verify={t.verify_passed} '
                        f'plan={t.plan_doc_written}({t.plan_doc_size}) '
                        f'reads_before={t.read_calls_before_edit} '
                        f'turns={t.total_turns} cost=${t.cost_usd:.3f}{err}'
                    )

    def _fmt_cell(values: list[int]) -> str:
        if not values:
            return '---'
        rate = sum(values) / len(values)
        return f'{rate:.0%} ({sum(values)}/{len(values)})'

    print(f'\n=== first_edit_success_rate (按 group × mode) ===')
    print(f'{"group":10} ' + ' '.join(f'{m:>16}' for m in modes))
    for grp in ('simple', 'complex'):
        row = [f'{grp:10}']
        for m in modes:
            row.append(f'{_fmt_cell(cell_first.get((grp, m), [])):>16}')
        print(' '.join(row))

    print(f'\n=== verify_passed_rate (按 group × mode) ===')
    print(f'{"group":10} ' + ' '.join(f'{m:>16}' for m in modes))
    for grp in ('simple', 'complex'):
        row = [f'{grp:10}']
        for m in modes:
            row.append(f'{_fmt_cell(cell_verify.get((grp, m), [])):>16}')
        print(' '.join(row))

    print(f'\n输出 → {out_path}')


if __name__ == '__main__':
    main()
