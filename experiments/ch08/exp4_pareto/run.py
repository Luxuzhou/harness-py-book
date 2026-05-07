"""
Accuracy × Cost Pareto 前沿分析
================================
对应书稿 8.8。在 (Accuracy, Cost) 二维平面上标定不同配置，
识别 Pareto 前沿上的最优改动。

流程：
  1. 在多个 Subject × Version 组合上跑 Capture-only Eval
  2. 每个组合产出 (avg_accuracy, avg_cost) 一个点
  3. Pareto 前沿 = 没有被其他点同时在两个维度上支配的点

用法：
    python run.py --smoke              # 5 tasks × 1 seed（快速验证结构）
    python run.py                      # 全量
    python run.py --subjects system_prompt  # 只跑指定 Subject
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# ── 环境 ──
_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

_resolved_key = (os.environ.get('DEEPSEEK_API_KEY')
                 or os.environ.get('HARNESS_API_KEY')
                 or os.environ.get('OPENAI_API_KEY') or '')
if _resolved_key:
    os.environ.setdefault('DEEPSEEK_API_KEY', _resolved_key)
_resolved_base = (os.environ.get('DEEPSEEK_BASE_URL')
                  or os.environ.get('HARNESS_BASE_URL')
                  or os.environ.get('OPENAI_BASE_URL') or '')
if _resolved_base:
    os.environ.setdefault('DEEPSEEK_BASE_URL', _resolved_base)

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / 'experiments' / 'ch08'))
sys.path.insert(0, str(_REPO_ROOT / 'experiments' / 'ch08' / 'exp1_eval_framework_extended'))

from framework import (
    Task,
    _build_capture_registry,
    _EVAL_SANDBOX,
    prepare_eval_sandbox,
    score,
)
from harness_py_pro import run as engine_run
from harness_py_pro.config import AgentConfig, ModelConfig

EXP_DIR = Path(__file__).parent
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
TASKS_FILE = (EXP_DIR.parent / 'exp1_eval_framework_extended'
              / 'fixtures' / 'system_prompt_tasks.jsonl')
CH4_GOLDEN = _REPO_ROOT / 'experiments' / 'ch04' / 'exp1_tool_description_eval' / 'golden_set.jsonl'


@dataclass
class ParetoPoint:
    subject_name: str
    subject_version: str
    n: int
    first_call_acc: float
    policy_pass_rate: float
    forbidden_call_rate: float
    avg_cost_usd: float
    avg_tool_calls: float
    avg_tokens: float


def load_subject(name: str, version: str):
    if name == 'system_prompt':
        from subjects.system_prompt import SystemPromptSubject
        return SystemPromptSubject(name=name, version=version)
    if name == 'tool_description':
        from subjects.tool_description import ToolDescriptionSubject
        return ToolDescriptionSubject(name=name, version=version)
    raise ValueError(f"Unknown subject: {name}")


def load_tasks(subject_name: str) -> list[Task]:
    if subject_name == 'tool_description' and CH4_GOLDEN.exists():
        raw = [json.loads(line) for line in CH4_GOLDEN.read_text(encoding='utf-8').splitlines() if line.strip()]
        # Ch4 golden_set 用 task/expected_tool/forbidden_tools 字段名
        tasks = []
        for r in raw:
            tasks.append(Task(
                id=r.get('id', '?'),
                user_prompt=r.get('user_prompt', r.get('task', '')),
                category=r.get('category', ''),
                expected_first_call=r.get('expected_first_call', r.get('expected_tool')),
                expected_calls=r.get('expected_calls', []),
                expected_contains=r.get('expected_contains', []),
                forbidden_calls=r.get('forbidden_calls', r.get('forbidden_tools', [])),
                forbidden_contains=r.get('forbidden_contains', []),
                notes=r.get('notes', ''),
            ))
        return tasks
    return Task.from_jsonl(TASKS_FILE)


def run_one(subject, task: Task, seed: int,
            model: str = 'deepseek-chat') -> dict:
    """Execute one eval task and return full metrics including cost."""
    captured: list[dict] = []
    err: str | None = None
    t0 = time.time()

    mc = ModelConfig(
        model=model,
        api_key=os.environ.get('DEEPSEEK_API_KEY', ''),
        base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
        context_window=64000,
        temperature=0.0,
        seed=seed,
    )
    ac = AgentConfig(
        cwd=_EVAL_SANDBOX,
        max_iterations=5,
        planning_turns=0,
        allow_write=True,
        allow_shell=True,
        sandbox_mode='bypass',
        network_isolated=True,
    )
    ac = subject.configure_agent(ac)

    prepare_eval_sandbox()
    registry = _build_capture_registry(captured)

    try:
        result = engine_run(
            task=task.user_prompt,
            model_config=mc,
            agent_config=ac,
            tool_registry=registry,
            verbose=False,
        )
        final_text = result.output or ''
        cost_usd = result.cost_usd
        total_tokens = result.total_tokens
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        final_text = ''
        cost_usd = 0.0
        total_tokens = 0

    all_calls = [c['name'] for c in captured]
    first = all_calls[0] if all_calls else None

    # Build Observation-like dict for score()
    obs = {
        'first_call': first,
        'all_calls': all_calls,
        'final_text': final_text,
        'matched_expected_first_call': (
            task.expected_first_call is not None and
            first == task.expected_first_call
        ),
        'matched_expected_calls': all(
            c in all_calls for c in task.expected_calls
        ) if task.expected_calls else True,
        'matched_expected_contains': all(
            s in final_text for s in task.expected_contains
        ) if task.expected_contains else True,
        'hit_forbidden_calls': any(
            c in all_calls for c in task.forbidden_calls
        ),
        'hit_forbidden_contains': any(
            s in final_text for s in task.forbidden_contains
        ),
    }
    sc = score(type('obs', (), obs)())  # score() expects an Observation-like object

    return {
        'task_id': task.id,
        'seed': seed,
        'first_call': first,
        'cost_usd': cost_usd,
        'total_tokens': total_tokens,
        'tool_calls': len(all_calls),
        **sc,
        'error': err,
    }


def aggregate(results: list[dict]) -> ParetoPoint:
    n = len(results)
    return ParetoPoint(
        subject_name=results[0]['subject_name'],
        subject_version=results[0]['subject_version'],
        n=n,
        first_call_acc=round(sum(r['first_call_ok'] for r in results) / n, 3),
        policy_pass_rate=round(sum(r['policy_ok'] for r in results) / n, 3),
        forbidden_call_rate=round(sum(r['forbidden_call_hit'] for r in results) / n, 3),
        avg_cost_usd=round(sum(r['cost_usd'] for r in results) / n, 5),
        avg_tool_calls=round(sum(r['tool_calls'] for r in results) / n, 2),
        avg_tokens=round(sum(r['total_tokens'] for r in results) / n, 1),
    )


def find_pareto_frontier(points: list[ParetoPoint]) -> list[ParetoPoint]:
    """Return points on the Pareto frontier (higher accuracy, lower cost is better).

    一个点支配另一个点当且仅当它在 accuracy 上 >= 对方 且 cost 上 <= 对方，
    且至少有一项严格更优。
    """
    frontier = []
    for i, p in enumerate(points):
        dominated = False
        for j, q in enumerate(points):
            if i == j:
                continue
            # q 是否支配 p？
            q_better_acc = q.first_call_acc >= p.first_call_acc
            q_better_cost = q.avg_cost_usd <= p.avg_cost_usd
            q_strict = (q.first_call_acc > p.first_call_acc or
                        q.avg_cost_usd < p.avg_cost_usd)
            if q_better_acc and q_better_cost and q_strict:
                dominated = True
                break
        if not dominated:
            frontier.append(p)
    return sorted(frontier, key=lambda p: (-p.first_call_acc, p.avg_cost_usd))


def format_table(points: list[ParetoPoint], frontier_names: set[str]) -> str:
    lines = [
        f"{'配置':<30} {'n':>4} {'First-call':>10} {'PolicyPass':>10} "
        f"{'Forbidden':>10} {'Cost($)':>10} {'工具调用':>8} {'前沿':>6}"
    ]
    lines.append('─' * 90)
    for p in points:
        tag = ' ◆' if f"{p.subject_name}/{p.subject_version}" in frontier_names else ''
        lines.append(
            f"{p.subject_name}/{p.subject_version:<28} {p.n:>4} "
            f"{p.first_call_acc:>8.1%}  {p.policy_pass_rate:>8.1%}  "
            f"{p.forbidden_call_rate:>8.1%}  {p.avg_cost_usd:>8.5f}  "
            f"{p.avg_tool_calls:>5.1f}    {tag}"
        )
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true',
                    help='5 tasks × 1 seed 快速验证')
    ap.add_argument('--subjects', nargs='+',
                    default=['system_prompt', 'tool_description'],
                    choices=['system_prompt', 'tool_description'])
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    ap.add_argument('--max-tasks', type=int, default=0,
                    help='限制每个 Subject 的任务数（0 = 全部）')
    args = ap.parse_args()

    configs = []
    for subj_name in args.subjects:
        for ver in ['v1', 'v2']:
            configs.append((subj_name, ver))

    all_results: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for subj_name, ver in configs:
        subject = load_subject(subj_name, ver)
        tasks = load_tasks(subj_name)
        seeds = [args.seeds[0]] if args.smoke else args.seeds
        if args.smoke:
            tasks = tasks[:5]
        if args.max_tasks > 0:
            tasks = tasks[:args.max_tasks]

        total = len(tasks) * len(seeds)
        print(f"\n=== {subj_name} {ver}  tasks={len(tasks)} seeds={seeds} ===")

        with subject:
            for task in tasks:
                for seed in seeds:
                    result = run_one(subject, task, seed)
                    result['subject_name'] = subj_name
                    result['subject_version'] = ver
                    all_results[(subj_name, ver)].append(result)

                    n = len(all_results[(subj_name, ver)])
                    tag = '✓' if result['first_call_ok'] else '✗'
                    cost_str = f"${result['cost_usd']:.4f}"
                    err = f" ERR={result['error'][:40]}" if result.get('error') else ''
                    print(f"  [{n:>3}/{total}] {task.id} seed={seed} {tag} "
                          f"first={result['first_call']} cost={cost_str}{err}")

    # 聚合
    points: list[ParetoPoint] = []
    for (subj_name, ver), results in sorted(all_results.items()):
        pt = aggregate(results)
        points.append(pt)

    # Pareto 前沿
    frontier = find_pareto_frontier(points)
    frontier_names = {f"{p.subject_name}/{p.subject_version}" for p in frontier}

    print(f"\n{'='*90}")
    print("Pareto 前沿分析：Accuracy × Cost")
    print(f"{'='*90}")
    print()
    print(format_table(points, frontier_names))
    print()
    print(f"Pareto 前沿上的配置（◆标记）：{len(frontier)} 个")
    for p in frontier:
        print(f"  ◆ {p.subject_name}/{p.subject_version}: "
              f"acc={p.first_call_acc:.1%} cost=${p.avg_cost_usd:.5f}")
    print()
    if len(frontier) < len(points):
        dominated = [p for p in points if p not in frontier]
        for p in dominated:
            print(f"  · {p.subject_name}/{p.subject_version}: "
                  f"被前沿支配 (acc={p.first_call_acc:.1%} cost=${p.avg_cost_usd:.5f})")

    # 保存结构化结果
    out = {
        'points': [{
            'subject_name': p.subject_name,
            'subject_version': p.subject_version,
            'n': p.n,
            'first_call_acc': p.first_call_acc,
            'policy_pass_rate': p.policy_pass_rate,
            'forbidden_call_rate': p.forbidden_call_rate,
            'avg_cost_usd': p.avg_cost_usd,
            'avg_tool_calls': p.avg_tool_calls,
            'avg_tokens': p.avg_tokens,
            'on_frontier': f"{p.subject_name}/{p.subject_version}" in frontier_names,
        } for p in points],
        'frontier': [{
            'subject_name': p.subject_name,
            'subject_version': p.subject_version,
        } for p in frontier],
    }
    summary_path = RESULTS / 'pareto_summary.json'
    summary_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"\n结果已写入 {summary_path}")


if __name__ == '__main__':
    main()
