"""
实验三：禁令措辞 vs 正向措辞的遵从率
=======================================
对应书稿 5.1.2 节"精简 AGENTS.md 的四类关键信息"中"明确的禁令"段落。

两种模式：
- clean：单轮任务从零写代码，无诱导上下文。强模型下违反率几乎总是 0%，
  但可借 `analyze_convergence.py` 观察方案收敛度。
- seeded：上下文里已有一段违规代码（如 os.system、eval），任务为"参考
  已有风格添加新函数"。此时违规更可能被触发，测得出措辞的真正效力。

用法：
    python run.py --smoke                    # 2对×2措辞×2次（clean）
    python run.py                            # 5对×2措辞×10次 = 100次（clean）
    python run.py --mode seeded              # 100次（seeded 诱导版）
    python run.py --mode seeded --n 5
    python run.py --pairs eval_usage,print_debug
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# === 加载 .env ===
_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(_REPO_ROOT))

from harness_py.config import ModelConfig  # noqa: E402
from harness_py.http_client import LLMClient  # noqa: E402

EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures'
RESULTS_DIR = EXP_DIR / 'results'


def load_pairs() -> list[dict]:
    return json.loads((FIXTURES / 'pairs.json').read_text(encoding='utf-8'))


def build_system_prompt(rule: str) -> str:
    """构造极简 system prompt，把规则放在最显眼的位置。"""
    return (
        'You are a Python code generator. You write production-quality Python functions.\n'
        '\n'
        '## Project rule (must follow)\n'
        f'{rule}\n'
        '\n'
        '## Output format\n'
        '- Output ONLY the requested function definition.\n'
        '- Do NOT include explanations, comments about the rule, or example usage.\n'
        '- Do NOT wrap the code in markdown fences unless necessary.\n'
    )


def check_violation(code: str, violation_patterns: list[str]) -> tuple[bool, list[str]]:
    """返回 (是否违反, 命中的pattern列表)。"""
    hits = [p for p in violation_patterns if re.search(p, code)]
    return bool(hits), hits


def check_compliance(code: str, compliance_patterns: list[str]) -> bool:
    """检查是否使用了推荐的替代方案。"""
    return any(re.search(p, code) for p in compliance_patterns)


def extract_code(text: str) -> str:
    """从 assistant 返回内容中抽出代码。
    兼容三种情况：纯代码、单块 ```python ... ```、多块合并。
    """
    # 优先匹配 markdown 代码块
    fence_pat = re.compile(r'```(?:python|py)?\s*\n(.*?)```', re.DOTALL)
    blocks = fence_pat.findall(text)
    if blocks:
        return '\n\n'.join(blocks)
    # 退化为整个文本
    return text


def build_user_message(pair: dict, mode: str) -> str:
    """根据模式构造 user message。
    - clean：用 pair['task']
    - seeded：读 pair['seeded_file'] 内容，填入 pair['seeded_task'] 的 {SEEDED_CODE}
    """
    if mode == 'clean':
        return pair['task']
    if mode == 'seeded':
        seeded_path = FIXTURES / pair['seeded_file']
        seeded_code = seeded_path.read_text(encoding='utf-8')
        return pair['seeded_task'].replace('{SEEDED_CODE}', seeded_code)
    raise ValueError(f'unknown mode: {mode}')


def run_trial(
    client: LLMClient,
    pair: dict,
    wording: str,
    mode: str,
    trial_idx: int,
) -> dict:
    """跑一次 trial，返回是否违反+命中的pattern。"""
    rule = pair[f'{wording}_rule']  # 'negative_rule' or 'positive_rule'
    system_prompt = build_system_prompt(rule)
    user_msg = build_user_message(pair, mode)
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_msg},
    ]

    t0 = time.time()
    try:
        resp = client.complete(messages)
        content = resp.get('content', '') or ''
        err = None
    except Exception as exc:
        content = ''
        err = f'{type(exc).__name__}: {exc}'
    duration = time.time() - t0

    code = extract_code(content)
    violated, hit_patterns = check_violation(code, pair['violation_patterns'])
    complied = check_compliance(code, pair['expected_compliance_patterns'])

    return {
        'pair_id': pair['id'],
        'wording': wording,
        'mode': mode,
        'trial': trial_idx,
        'violated': violated,
        'complied_with_alternative': complied,
        'hit_patterns': hit_patterns,
        'code_length': len(code),
        'duration_sec': round(duration, 2),
        'error': err,
        # 保留前400字节方便人工抽查
        'code_preview': code[:400],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true', help='2对×2措辞×2次')
    parser.add_argument('--pairs', default='all', help='逗号分隔的 pair id 或 all')
    parser.add_argument('--n', type=int, default=10, help='每措辞重复次数')
    parser.add_argument('--mode', choices=['clean', 'seeded'], default='clean',
                        help='clean=从零写；seeded=诱导上下文（已有违规代码）')
    parser.add_argument('--sleep', type=float, default=1.0)
    parser.add_argument('--out', default=None, help='输出文件名，默认按 mode 分文件')
    args = parser.parse_args()
    if args.out is None:
        args.out = f'results_{args.mode}.json'

    RESULTS_DIR.mkdir(exist_ok=True)
    all_pairs = load_pairs()

    if args.smoke:
        pairs = all_pairs[:2]
        n = 2
    else:
        if args.pairs == 'all':
            pairs = all_pairs
        else:
            wanted = {p.strip() for p in args.pairs.split(',')}
            pairs = [p for p in all_pairs if p['id'] in wanted]
        n = args.n

    mc = ModelConfig.from_env()
    if not mc.api_key:
        print('ERROR: 未设置 API key。')
        return 1
    # temperature 保留一点以产生样本间差异（严格确定性下所有 trial 会一样）
    mc.temperature = 0.3

    client = LLMClient(mc)
    out_path = RESULTS_DIR / args.out

    all_results: list[dict] = []
    t_start = time.time()
    total = len(pairs) * 2 * n
    done = 0

    for pair in pairs:
        print(f'\n=== {pair["id"]}（{pair["topic"]}） ===')
        for wording in ('negative', 'positive'):
            rule_desc = pair[f'{wording}_rule']
            print(f'  措辞[{wording}]: {rule_desc[:50]}...')
            for i in range(1, n + 1):
                done += 1
                result = run_trial(client, pair, wording, args.mode, i)
                all_results.append(result)
                flag = '[X] 违反' if result['violated'] else '[OK] 合规'
                alt = ' | 用替代' if result['complied_with_alternative'] else ''
                err_note = f' ERR={result["error"]}' if result['error'] else ''
                print(
                    f'    [{done:>3}/{total}] trial{i} {flag}{alt} '
                    f'code={result["code_length"]}B '
                    f'time={result["duration_sec"]:.1f}s{err_note}',
                    flush=True,
                )
                out_path.write_text(
                    json.dumps(all_results, ensure_ascii=False, indent=2),
                    encoding='utf-8',
                )
                if args.sleep > 0:
                    time.sleep(args.sleep)

    elapsed = time.time() - t_start
    print(f'\n完成 {done} 次调用，用时 {elapsed:.0f}s')

    # 汇总
    print('\n=== 违反率汇总 ===')
    print(f'{"pair_id":<20}{"negative":>12}{"positive":>12}{"差值":>12}')
    for pair in pairs:
        neg = [r for r in all_results if r['pair_id'] == pair['id'] and r['wording'] == 'negative' and r['error'] is None]
        pos = [r for r in all_results if r['pair_id'] == pair['id'] and r['wording'] == 'positive' and r['error'] is None]
        neg_rate = sum(1 for r in neg if r['violated']) / len(neg) * 100 if neg else 0
        pos_rate = sum(1 for r in pos if r['violated']) / len(pos) * 100 if pos else 0
        diff = pos_rate - neg_rate
        print(f'{pair["id"]:<20}{neg_rate:>10.1f}%{pos_rate:>11.1f}%{diff:>+10.1f}%')

    return 0


if __name__ == '__main__':
    sys.exit(main())
