"""
exp2：闭环验证 vs 开环 vs Agent 自决
==========================================
对应书稿 7.2 节论点 L2：Harness 强制独立跑 pytest 比让 Agent 自决跑测试更稳定。

三档对照：
  O1_no_bash      : Agent 仅 read_file + edit_file（无 bash），改完即报告
  O2_bash_optional: Agent 有 read+edit+bash，prompt 不强制跑测试
  O3_harness_forced: Agent 仅 read+edit（无 bash），框架在 Agent 报告完成后跑 pytest，
                    失败则把 pytest stderr 作为 user message 启动一次重试

任务集：复用 exp1 的 5 个 fixture（每个含 prompt-reported bug A + hidden bug B）

样本：
  smoke：5 任务 × 3 档 × 1 seed = 15 trials
  全量：5 任务 × 3 档 × 3 seeds = 45 trials
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
TASKS_DIR = EXP_DIR.parent / 'exp1_self_eval_blindspot' / 'tasks'  # 复用 exp1 任务集
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
WORKDIR = EXP_DIR / 'workdir'
WORKDIR.mkdir(exist_ok=True)

MAX_TURNS_FIRST = 8
MAX_TURNS_RETRY = 4  # O3 retry 时给的轮数

DONE_KEYWORDS = [
    '任务完成', '修复完成', '已完成', '完成修复', '已修复',
    'task complete', 'fixed', 'done',
]

CONDITIONS = {
    'O1_no_bash':       {'tools': ['read_file', 'edit_file'],          'has_retry': False},
    'O2_bash_optional': {'tools': ['read_file', 'edit_file', 'bash'],  'has_retry': False},
    'O3_harness_forced':{'tools': ['read_file', 'edit_file'],          'has_retry': True},
}


@dataclass
class Trial:
    task_id: str
    category: str
    condition: str
    seed: int
    pytest_pass: int
    self_report_done: int
    final_turns: int
    tool_calls: int
    cost_usd: float
    retry_triggered: int      # O3 是否触发重试
    bash_calls: int           # O2 用了几次 bash
    wall_seconds: float
    error: str = ''


def load_tasks() -> list[dict]:
    tasks = []
    for task_dir in sorted(TASKS_DIR.iterdir()):
        if not task_dir.is_dir():
            continue
        meta_path = task_dir / 'meta.json'
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        meta['_dir'] = task_dir
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
    shutil.copytree(task['_dir'], work,
                    ignore=shutil.ignore_patterns('meta.json'))
    return work


def run_pytest(workdir: Path) -> tuple[int, str]:
    """跑 pytest；用 bytes 模式 + 容错解码，避免 Windows GBK 解码报错。"""
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=short'],
            cwd=workdir,
            capture_output=True,
            timeout=30,
        )
        out = proc.stdout.decode('utf-8', errors='replace')
        err = proc.stderr.decode('utf-8', errors='replace')
        return proc.returncode, (out + err)
    except Exception as e:
        return -1, f'pytest 启动失败: {e}'


def is_done(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(kw.lower() in lower for kw in DONE_KEYWORDS)


def count_bash_calls(workdir: Path, session_id: str) -> int:
    sf = workdir / '.harness_sessions' / f'{session_id}.jsonl'
    if not sf.exists():
        return 0
    n = 0
    for line in sf.read_text(encoding='utf-8').splitlines():
        try:
            ev = json.loads(line)
            if ev.get('type') == 'tool_call' and ev.get('tool') == 'bash':
                n += 1
        except Exception:
            pass
    return n


def run_one(task: dict, condition: str, seed: int) -> Trial:
    cond_cfg = CONDITIONS[condition]
    run_id = f"{task['id']}_{condition}_seed{seed}"
    workdir = setup_workspace(task, run_id)

    ac = AgentConfig(
        cwd=workdir,
        max_iterations=MAX_TURNS_FIRST,
        planning_turns=0,
        allow_write=True,
        allow_shell='bash' in cond_cfg['tools'],
        sandbox_mode='bypass',
        network_isolated=True,
        tool_filter=list(cond_cfg['tools']),
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
    retry_triggered = 0
    session_id = ''

    try:
        result = engine_run(
            task=task['user_prompt'],
            model_config=mc,
            agent_config=ac,
            verbose=False,
        )
        final_msg = (result.output or '')
        turns = result.turns
        tool_calls = result.tool_calls
        cost = result.cost_usd
        session_id = result.session_id
    except Exception as e:
        err = f'{type(e).__name__}: {e}'

    # O3：框架强制跑 pytest，失败则注入回灌一次
    if cond_cfg['has_retry']:
        code, output = run_pytest(workdir)
        if code != 0:
            retry_triggered = 1
            # 再跑一轮，把 pytest 报告作为新的 user prompt
            ac2 = AgentConfig(
                cwd=workdir,
                max_iterations=MAX_TURNS_RETRY,
                planning_turns=0,
                allow_write=True,
                allow_shell=False,
                sandbox_mode='bypass',
                network_isolated=True,
                tool_filter=list(cond_cfg['tools']),
            )
            retry_prompt = (
                f"你刚才报告任务完成，但框架独立跑 pytest 时仍有失败。\n"
                f"原任务：{task['user_prompt']}\n\n"
                f"pytest 输出：\n{output[-1500:]}\n\n"
                f"请继续修复使所有测试通过。修复完成后告诉我'任务完成'。"
            )
            try:
                result2 = engine_run(
                    task=retry_prompt,
                    model_config=mc,
                    agent_config=ac2,
                    verbose=False,
                )
                final_msg = result2.output or final_msg
                turns += result2.turns
                tool_calls += result2.tool_calls
                cost += result2.cost_usd
            except Exception as e:
                err = err or f'retry-{type(e).__name__}: {e}'

    bash_n = count_bash_calls(workdir, session_id) if session_id else 0
    code, _ = run_pytest(workdir)
    pytest_pass = int(code == 0)
    self_done = is_done(final_msg)

    return Trial(
        task_id=task['id'],
        category=task['category'],
        condition=condition,
        seed=seed,
        pytest_pass=pytest_pass,
        self_report_done=int(self_done),
        final_turns=turns,
        tool_calls=tool_calls,
        cost_usd=round(cost, 4),
        retry_triggered=retry_triggered,
        bash_calls=bash_n,
        wall_seconds=round(time.time() - t0, 2),
        error=err,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    ap.add_argument('--conditions', nargs='+', default=list(CONDITIONS.keys()))
    ap.add_argument('--out', default='raw.jsonl')
    args = ap.parse_args()

    seeds = [args.seeds[0]] if args.smoke else args.seeds
    tasks = load_tasks()
    total = len(tasks) * len(args.conditions) * len(seeds)
    print(f'=== exp2 pytest closure ===')
    print(f'  tasks={len(tasks)} conditions={args.conditions} seeds={seeds}  共 {total}')

    out_path = RESULTS / args.out
    n = 0
    cond_pass: dict[str, list[int]] = {c: [] for c in args.conditions}
    with out_path.open('w', encoding='utf-8') as fh:
        for task in tasks:
            for cond in args.conditions:
                for seed in seeds:
                    n += 1
                    t = run_one(task, cond, seed)
                    fh.write(json.dumps(asdict(t), ensure_ascii=False) + '\n')
                    fh.flush()
                    cond_pass[cond].append(t.pytest_pass)
                    err = f' ERR={t.error[:30]}' if t.error else ''
                    print(
                        f'  [{n:>2}/{total}] {t.task_id:18} {t.condition:18} seed={seed} '
                        f'{"PASS" if t.pytest_pass else "FAIL"} '
                        f'turns={t.final_turns:>2} bash={t.bash_calls} '
                        f'retry={t.retry_triggered} cost=${t.cost_usd:.3f}{err}'
                    )

    print(f'\n=== 汇总 ===')
    for cond, ps in cond_pass.items():
        if ps:
            print(f'  {cond:18}  pass_rate = {sum(ps)}/{len(ps)} = {sum(ps)/len(ps):.1%}')
    print(f'\n输出 → {out_path}')


if __name__ == '__main__':
    main()
