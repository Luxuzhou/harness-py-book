"""
Solo vs Dual vs Quad Agent 对照实验
=====================================
对应书稿 11.6。同一任务 × 3 档 Agent 配置 × 3 seeds，复刻 Anthropic 的
"Solo $9 vs Multi $200" 实验。

设计：
  自变量：config ∈ {solo, dual, quad}
  因变量：total_cost_usd, total_turns, task_resolved, context_overflow_events,
          contract_consistency, wall_seconds
  样本：
    --smoke:  solo + dual × 1 seed = 2
    full:     solo + dual + quad × 3 seeds = 9

用法：
    python run.py --smoke
    python run.py
    python run.py --config quad --seeds 42
"""
from __future__ import annotations

import argparse
import json
import os
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

EXP_DIR = Path(__file__).parent
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
CASE_DIR = _REPO_ROOT / 'cases' / 'multiagent_enterprise'


@dataclass
class Result:
    config: str                       # solo | dual | quad
    seed: int
    total_cost_usd: float
    total_turns: int                  # 所有 Agent 累计
    task_resolved: int                # QA 最终验收 = 1
    context_overflow_events: int
    contract_consistency: int         # 1 = Java/Python 接口字段一致
    wall_seconds: float
    per_agent_breakdown: dict         # {agent_name: {turns, cost, tokens}}
    error: str = ''


def run_solo(seed: int, task_md: str) -> Result:
    """单 Agent 全能配置：6 工具全开，cwd = case 根。"""
    raise NotImplementedError(
        "run_solo() 待接入：用 harness_py_pro.engine.run() 单 Agent 跑 task_md，"
        "max_turns=60"
    )


def run_dual(seed: int, task_md: str) -> Result:
    """双 Agent：Developer + QA，QA 在 Developer 自报完成后做验收。"""
    raise NotImplementedError(
        "run_dual() 待接入：用 harness_py_pro.swarm.orchestrate() 配两个 AgentRole"
    )


def run_quad(seed: int, task_md: str) -> Result:
    """四 Agent：直接复用 cases/multiagent_enterprise/run.py 的配置。"""
    raise NotImplementedError(
        "run_quad() 待接入：直接 import cases/multiagent_enterprise/run.py 的 main(seed)"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--config', choices=['solo', 'dual', 'quad', 'all'], default='all')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    args = ap.parse_args()

    task_file = CASE_DIR / 'TASK.md'
    if not task_file.exists():
        sys.exit(f"未找到任务描述：{task_file}")
    task_md = task_file.read_text(encoding='utf-8')

    if args.smoke:
        configs = ['solo', 'dual']
        seeds = [args.seeds[0]]
    else:
        configs = ['solo', 'dual', 'quad'] if args.config == 'all' else [args.config]
        seeds = args.seeds

    runners = {'solo': run_solo, 'dual': run_dual, 'quad': run_quad}
    total = len(configs) * len(seeds)
    print(f"=== Ch11 exp1 Solo vs Dual vs Quad ===")
    print(f"  configs={configs} seeds={seeds}  共 {total} 次完整运行")
    print(f"  任务：{task_file}")

    out_path = RESULTS / 'raw.jsonl'
    n = 0
    with out_path.open('w', encoding='utf-8') as fh:
        for cfg in configs:
            for seed in seeds:
                n += 1
                t0 = time.time()
                try:
                    r = runners[cfg](seed, task_md)
                    r.wall_seconds = round(time.time() - t0, 2)
                except NotImplementedError as e:
                    r = Result(config=cfg, seed=seed, total_cost_usd=0,
                               total_turns=0, task_resolved=0,
                               context_overflow_events=0, contract_consistency=0,
                               wall_seconds=round(time.time() - t0, 2),
                               per_agent_breakdown={},
                               error=str(e))
                except Exception as e:
                    r = Result(config=cfg, seed=seed, total_cost_usd=0,
                               total_turns=0, task_resolved=0,
                               context_overflow_events=0, contract_consistency=0,
                               wall_seconds=round(time.time() - t0, 2),
                               per_agent_breakdown={},
                               error=f'{type(e).__name__}: {e}')
                fh.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')
                fh.flush()
                flag = 'PASS' if r.task_resolved else 'FAIL'
                err = f' ERR={r.error[:40]}' if r.error else ''
                print(f"  [{n:>2}/{total}] {cfg:5} seed={seed} {flag} cost=${r.total_cost_usd:.2f} turns={r.total_turns}{err}")

    print(f"\n完成 → {out_path}")


if __name__ == '__main__':
    main()
