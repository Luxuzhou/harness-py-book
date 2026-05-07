"""
exp4：LoopGuard 三层防御边际价值
=====================================
对应书稿 7.4 节论点 L4：LoopGuard 在死循环场景下省 token + 诱导切换策略，
不一定提升任务成功率，但价值在于"前两层（自检 + budget）失效时的兜底"。

四档对照：
  D0_naked       : LoopGuard 完全禁用，turn budget = 25
  D1_budget_only : 仅 turn budget = 15（业界最常见的最低保障）
  D2_with_guard  : turn budget = 15 + LoopGuard 启用
  D3_full        : turn budget = 15 + LoopGuard + 介入后注入 reflection 提示

诱导 fixture（先做 F1 验证设计可行性）：
  F1_pytest_garble: pytest 输出夹杂乱码，模拟 DeepSeek 69 次重试场景

核心指标：
  - task_resolved（最终 pytest 是否通过）
  - tool_calls_total（总成本代理）
  - intervention_count（D2/D3 中 guard 触发了几次）
  - strategy_switched（介入后是否切换工具/方法）
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

from harness_py_pro.config import AgentConfig, ModelConfig, HookConfig
from harness_py_pro.engine import run as engine_run
from harness_py_pro import loop_guard as _loop_guard_mod
import harness_py_pro.engine as _engine_mod


# ---------- 诱导 hook：让 edit_file 工具前 N 次失败 ----------
def make_evil_edit_hook(fail_first_n: int):
    """模拟 DeerFlow #1261 的"工具反馈不可靠"场景。

    前 fail_first_n 次 edit_file 调用强制返回固定错误，第 N+1 次起放行。
    返回的错误信息完全一致（每次相同），让 LoopGuard 的 hash 检测在第 3 次能命中。
    """
    state = {'edit_calls': 0}

    def pre_tool(tool_name: str, tool_args: dict, config_dict: dict):
        if tool_name != 'edit_file':
            return True, ''
        state['edit_calls'] += 1
        if state['edit_calls'] <= fail_first_n:
            return False, 'Tool transient error: please retry'
        return True, ''

    return pre_tool


def make_lock_in_hook(fail_first_n: int):
    """更激进的诱导：除了 edit_file 失败，bash 中能写文件的命令也拦截。

    Agent 没有"绕过 edit_file"的替代工具，被锁在反复 retry edit_file 的循环里。
    模拟 enterprise 场景下"prompt 强制只能用 edit_file"或"工具集本就受限"。
    """
    state = {'edit_calls': 0}

    def pre_tool(tool_name: str, tool_args: dict, config_dict: dict):
        if tool_name == 'edit_file':
            state['edit_calls'] += 1
            if state['edit_calls'] <= fail_first_n:
                return False, 'Tool transient error: please retry'
            return True, ''
        if tool_name == 'bash':
            cmd = tool_args.get('command', '')
            if any(kw in cmd for kw in ['sed ', 'sed\t', '>', 'tee ', 'cat <',
                                         'cp ', 'mv ', 'echo ']):
                return False, 'bash: write commands disabled in sandbox'
        return True, ''

    return pre_tool

EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
WORKDIR = EXP_DIR / 'workdir'
WORKDIR.mkdir(exist_ok=True)

# 各档的 turn budget
TURN_BUDGETS = {
    'D0_naked': 25,
    'D1_budget_only': 15,
    'D2_with_guard': 15,
    'D3_full': 15,
}


# ---------- LoopGuard 替换：NoOpGuard for D0/D1 ----------
class NoOpGuard:
    def __init__(self):
        self._total = 0

    def check(self, tool_name, tool_args, success, result_preview):
        self._total += 1
        return False, ''

    def reset(self):
        self._total = 0

    @property
    def stats(self):
        return {'total_calls': self._total, 'interventions': 0}


_REAL_GUARD = _loop_guard_mod.LoopGuard


def _set_defense(level: str):
    if level in ('D0_naked', 'D1_budget_only'):
        _engine_mod.LoopGuard = NoOpGuard
    else:
        _engine_mod.LoopGuard = _REAL_GUARD


@dataclass
class Trial:
    fixture_id: str
    category: str
    defense: str
    seed: int
    task_resolved: int
    final_turns: int
    tool_calls_total: int
    intervention_count: int
    intervention_turn_first: int
    bash_calls: int
    edit_calls: int
    read_calls: int
    write_calls: int
    edit_failures: int           # edit_file 调用中失败的次数
    strategy_switched: int       # 介入后是否切换了工具
    cost_usd: float
    wall_seconds: float
    error: str = ''


def setup_workspace(fixture_dir: Path, run_id: str) -> Path:
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
    shutil.copytree(fixture_dir, work,
                    ignore=shutil.ignore_patterns('meta.json'))
    return work


def run_pytest_clean(workdir: Path) -> int:
    """干净跑 pytest（移除 conftest 干扰），用于最终 ground truth。"""
    # 临时把 conftest 改名
    conftest = workdir / 'conftest.py'
    backup = workdir / 'conftest.py.bak'
    if conftest.exists():
        conftest.rename(backup)
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=no'],
            cwd=workdir,
            capture_output=True,
            timeout=30,
        )
        return proc.returncode
    except Exception:
        return -1
    finally:
        if backup.exists():
            backup.rename(conftest)


def parse_session(workdir: Path, session_id: str) -> dict:
    """从 session.jsonl 提取详细统计。"""
    sf = workdir / '.harness_sessions' / f'{session_id}.jsonl'
    out = {
        'first_intervention_turn': 0,
        'tool_seq': [],
        'bash_calls': 0,
        'edit_calls': 0,
        'read_calls': 0,
        'write_calls': 0,
        'edit_failures': 0,
    }
    if not sf.exists():
        return out
    turn = 0
    for line in sf.read_text(encoding='utf-8').splitlines():
        try:
            ev = json.loads(line)
        except Exception:
            continue
        if ev.get('type') == 'tool_call':
            turn += 1
            tool = ev.get('tool', '')
            out['tool_seq'].append(tool)
            if tool == 'bash':
                out['bash_calls'] += 1
            elif tool == 'edit_file':
                out['edit_calls'] += 1
                if not ev.get('ok', True):
                    out['edit_failures'] += 1
            elif tool == 'read_file':
                out['read_calls'] += 1
            elif tool == 'write_file':
                out['write_calls'] += 1
        elif ev.get('type') == 'loop_guard' and out['first_intervention_turn'] == 0:
            out['first_intervention_turn'] = turn
    return out


def detect_strategy_switch(tool_seq: list[str], intervention_turn: int) -> int:
    """介入后是否换了工具？把介入前 3 轮 vs 介入后 3 轮的工具集做对比。"""
    if intervention_turn == 0 or intervention_turn >= len(tool_seq):
        return 0
    before = set(tool_seq[max(0, intervention_turn - 3):intervention_turn])
    after = set(tool_seq[intervention_turn:intervention_turn + 3])
    if not after:
        return 0
    return int(bool(after - before))  # 介入后出现了新工具


def run_one(fixture_dir: Path, defense: str, seed: int) -> Trial:
    meta = json.loads((fixture_dir / 'meta.json').read_text(encoding='utf-8'))
    run_id = f"{meta['id']}_{defense}_seed{seed}"
    workdir = setup_workspace(fixture_dir, run_id)

    _set_defense(defense)

    # D3 在 prompt 中前置 reflection 提示（最简化的"D3_full"实现）
    prompt = meta['user_prompt']
    if defense == 'D3_full':
        prompt = (
            prompt + '\n\n注意：如果同样的命令重复执行多次返回相同/无意义结果，'
            '不要继续重试同一命令——换一种工具或方法（比如改用 read_file '
            '直接读测试文件、用 grep 搜索代码模式）。'
        )

    hooks = HookConfig()
    tool_filter: list[str] = []
    if meta.get('hook') == 'evil_edit':
        params = meta.get('hook_params', {})
        hooks = HookConfig(pre_tool=make_evil_edit_hook(
            int(params.get('fail_first_n', 4))))
        tool_filter = ['read_file', 'edit_file', 'bash', 'grep_search', 'glob_search']
    elif meta.get('hook') == 'lock_in':
        params = meta.get('hook_params', {})
        hooks = HookConfig(pre_tool=make_lock_in_hook(
            int(params.get('fail_first_n', 30))))
        tool_filter = ['read_file', 'edit_file', 'bash', 'grep_search', 'glob_search']

    ac = AgentConfig(
        cwd=workdir,
        max_iterations=TURN_BUDGETS[defense],
        planning_turns=0,
        allow_write=True,
        allow_shell=True,
        sandbox_mode='bypass',
        network_isolated=True,
        hooks=hooks,
        tool_filter=tool_filter,
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
    turns = 0
    tool_calls = 0
    cost = 0.0
    interventions = 0
    session_id = ''

    try:
        result = engine_run(
            task=prompt,
            model_config=mc,
            agent_config=ac,
            verbose=False,
        )
        turns = result.turns
        tool_calls = result.tool_calls
        cost = result.cost_usd
        interventions = (result.guard_stats or {}).get('interventions', 0)
        session_id = result.session_id
    except Exception as e:
        err = f'{type(e).__name__}: {e}'

    _set_defense('D2_with_guard')  # 复位

    sess = parse_session(workdir, session_id) if session_id else {}
    code = run_pytest_clean(workdir)

    return Trial(
        fixture_id=meta['id'],
        category=meta['category'],
        defense=defense,
        seed=seed,
        task_resolved=int(code == 0),
        final_turns=turns,
        tool_calls_total=tool_calls,
        intervention_count=interventions,
        intervention_turn_first=sess.get('first_intervention_turn', 0),
        bash_calls=sess.get('bash_calls', 0),
        edit_calls=sess.get('edit_calls', 0),
        read_calls=sess.get('read_calls', 0),
        write_calls=sess.get('write_calls', 0),
        edit_failures=sess.get('edit_failures', 0),
        strategy_switched=detect_strategy_switch(
            sess.get('tool_seq', []),
            sess.get('first_intervention_turn', 0),
        ),
        cost_usd=round(cost, 4),
        wall_seconds=round(time.time() - t0, 2),
        error=err,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    ap.add_argument('--defenses', nargs='+',
                    default=['D0_naked', 'D2_with_guard'])
    ap.add_argument('--fixture', default='all')
    ap.add_argument('--out', default='raw.jsonl')
    args = ap.parse_args()

    fixtures = sorted(d for d in FIXTURES.iterdir() if d.is_dir())
    if args.fixture != 'all':
        fixtures = [d for d in fixtures if d.name == args.fixture]
    if not fixtures:
        print('未找到 fixture'); return

    seeds = [args.seeds[0]] if args.smoke else args.seeds
    total = len(fixtures) * len(args.defenses) * len(seeds)
    print(f'=== exp4 LoopGuard layered defense ===')
    print(f'  fixtures={[d.name for d in fixtures]} defenses={args.defenses} '
          f'seeds={seeds}  共 {total} trials')

    out_path = RESULTS / args.out
    n = 0
    summary: dict[str, dict] = {d: {'resolved': 0, 'turns': 0, 'cost': 0.0,
                                     'interv': 0, 'switched': 0, 'n': 0}
                                for d in args.defenses}
    with out_path.open('w', encoding='utf-8') as fh:
        for fx in fixtures:
            for defense in args.defenses:
                for seed in seeds:
                    n += 1
                    t = run_one(fx, defense, seed)
                    fh.write(json.dumps(asdict(t), ensure_ascii=False) + '\n')
                    fh.flush()
                    s = summary[defense]
                    s['resolved'] += t.task_resolved
                    s['turns'] += t.final_turns
                    s['cost'] += t.cost_usd
                    s['interv'] += t.intervention_count
                    s['switched'] += t.strategy_switched
                    s['n'] += 1
                    err = f' ERR={t.error[:30]}' if t.error else ''
                    print(
                        f'  [{n:>2}/{total}] {t.fixture_id:18} {t.defense:16} '
                        f'seed={seed} {"PASS" if t.task_resolved else "FAIL"} '
                        f'turns={t.final_turns:>2} interv={t.intervention_count} '
                        f'first_turn={t.intervention_turn_first} '
                        f'bash={t.bash_calls} edit={t.edit_calls}(fail={t.edit_failures}) '
                        f'read={t.read_calls} write={t.write_calls} '
                        f'switched={t.strategy_switched} '
                        f'cost=${t.cost_usd:.3f}{err}'
                    )
    print(f'\n=== 汇总 ===')
    for d, s in summary.items():
        if s['n']:
            print(f"  {d:16}  resolved={s['resolved']}/{s['n']}  "
                  f"avg_turns={s['turns']/s['n']:.1f}  "
                  f"avg_cost=${s['cost']/s['n']:.3f}  "
                  f"interv={s['interv']}  switched={s['switched']}/{s['n']}")
    print(f'\n输出 → {out_path}')


if __name__ == '__main__':
    main()
