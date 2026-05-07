"""
跨层 Eval 实验主入口。

对应书稿 8.3。在 tool_description / system_prompt 两类 Subject 上跑同一套
Capture-only Runner，输出对照数据，证明 Eval 基础设施是反馈闭环的通用基石。

用法：
    python run.py --smoke
    python run.py
    python run.py --subject system_prompt --version v2
    python run.py --subject tool_description --golden-set ../../ch04/exp1_tool_description_eval/golden_set.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# 环境
_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

# API key 兼容：DEEPSEEK / HARNESS / OPENAI 任一即可，统一回填到 DEEPSEEK_API_KEY
_resolved_key = (os.environ.get('DEEPSEEK_API_KEY')
                 or os.environ.get('HARNESS_API_KEY')
                 or os.environ.get('OPENAI_API_KEY') or '')
if _resolved_key:
    os.environ['DEEPSEEK_API_KEY'] = _resolved_key
_resolved_base = (os.environ.get('DEEPSEEK_BASE_URL')
                  or os.environ.get('HARNESS_BASE_URL')
                  or os.environ.get('OPENAI_BASE_URL') or '')
if _resolved_base:
    os.environ['DEEPSEEK_BASE_URL'] = _resolved_base

from framework import Runner, Task, score  # noqa: E402

EXP_DIR = Path(__file__).parent
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
DEFAULT_TASKS = EXP_DIR / 'fixtures' / 'system_prompt_tasks.jsonl'
CH4_GOLDEN = _REPO_ROOT / 'experiments' / 'ch04' / 'exp1_tool_description_eval' / 'golden_set.jsonl'


def load_subject(name: str, version: str):
    if name == 'system_prompt':
        from subjects.system_prompt import SystemPromptSubject
        return SystemPromptSubject(name='system_prompt', version=version)
    if name == 'tool_description':
        from subjects.tool_description import ToolDescriptionSubject
        return ToolDescriptionSubject(name='tool_description', version=version)
    raise ValueError(f"Unknown subject: {name}")


def aggregate(observations) -> dict[tuple[str, str], dict[str, float]]:
    bag: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for o in observations:
        bag[(o.subject_name, o.subject_version)].append(score(o))
    out = {}
    for key, scores in bag.items():
        n = len(scores)
        out[key] = {
            'n': n,
            'first_call_acc': round(sum(s['first_call_ok'] for s in scores) / n, 3) if n else 0,
            'expected_calls_acc': round(sum(s['expected_calls_ok'] for s in scores) / n, 3) if n else 0,
            'contains_acc': round(sum(s['contains_ok'] for s in scores) / n, 3) if n else 0,
            'forbidden_call_rate': round(sum(s['forbidden_call_hit'] for s in scores) / n, 3) if n else 0,
            'policy_pass_rate': round(sum(s['policy_ok'] for s in scores) / n, 3) if n else 0,
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--subject', default='system_prompt',
                    choices=['system_prompt', 'tool_description'])
    ap.add_argument('--version', default='all',
                    help='指定单个版本（v1/v2），默认两个都跑')
    ap.add_argument('--golden-set', type=Path, default=None,
                    help='Golden Set jsonl 路径，默认 fixtures/system_prompt_tasks.jsonl')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    args = ap.parse_args()

    # Golden set
    golden = args.golden_set
    if golden is None:
        if args.subject == 'tool_description' and CH4_GOLDEN.exists():
            golden = CH4_GOLDEN
        else:
            golden = DEFAULT_TASKS
    tasks = Task.from_jsonl(golden)

    if args.smoke:
        tasks = tasks[:5]
        seeds = [args.seeds[0]]
    else:
        seeds = args.seeds

    versions = ['v1', 'v2'] if args.version == 'all' else [args.version]

    runner = Runner()
    all_obs = []
    for ver in versions:
        subject = load_subject(args.subject, ver)
        out_path = RESULTS / f'raw_{args.subject}_{ver}.jsonl'
        n = 0
        total = len(tasks) * len(seeds)
        print(f"=== Subject={args.subject} Version={ver}  tasks={len(tasks)} seeds={seeds} ===")
        with out_path.open('w', encoding='utf-8') as fh:
            for obs in runner.run(subject, tasks, seeds):
                n += 1
                fh.write(json.dumps(obs.__dict__, ensure_ascii=False) + '\n')
                fh.flush()
                all_obs.append(obs)
                tag = '✓' if (
                    obs.matched_expected_first_call
                    and obs.matched_expected_calls
                    and not obs.hit_forbidden_calls
                ) else '✗'
                err = f" ERR={obs.error}" if obs.error else ''
                print(f"  [{n:>3}/{total}] {obs.task_id} seed={obs.seed} {tag} first={obs.first_call}{err}")
        print(f"写入 {out_path}")

    # 聚合
    summary = aggregate(all_obs)
    summary_path = RESULTS / f'summary_{args.subject}.json'
    summary_path.write_text(
        json.dumps(
            {f"{k[0]}::{k[1]}": v for k, v in summary.items()},
            indent=2, ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    print(f"\n=== 总览 ===")
    for (sub, ver), m in summary.items():
        print(
            f"  {sub} {ver}  policy_pass={m['policy_pass_rate']:.1%}  "
            f"first_call={m['first_call_acc']:.1%}  "
            f"expected_calls={m['expected_calls_acc']:.1%}  "
            f"forbidden_call={m['forbidden_call_rate']:.1%}  n={m['n']}"
        )
    print(f"\n详见 {summary_path}")


if __name__ == '__main__':
    main()
