"""
一次性脚本：为公众号文章捕获 4 个关键 trial 的 probe 原始回答
====================================================================
书稿写完、文章发出后可删除此文件及其产物。

目的：exp1 的 run.py 只保存 quality_score 和 recall_accuracy 数字，
不保存 Agent 对 PROBE_QUESTION 的实际回答文本。文章需要展示
"off 路径下 Agent 说了什么 vs on 路径下 Agent 说了什么" 的现场
对比，所以要重跑 4 个关键 trial 并把 probe answer 写进独立文件。

输出：results/_article_probes.jsonl
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

EXP_DIR = Path(__file__).parent
_REPO_ROOT = EXP_DIR.parents[2]

# 加载 .env
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(EXP_DIR))

# 复用 run.py 的实验逻辑，不改动它
from run import (  # noqa: E402
    simulate_conversation, ask_probe, judge,
    MODULE_ORDER, compute_snr,
)
from harness_py.config import ModelConfig  # noqa: E402
from harness_py.http_client import LLMClient  # noqa: E402


def main():
    mc = ModelConfig.from_env()
    if not mc.api_key:
        print('ERROR: 未设置 HARNESS_API_KEY')
        sys.exit(2)
    mc.temperature = 0.3  # 对齐 run.py 的设置
    client = LLMClient(mc)

    # 只跑 turn=20 的 4 个关键 trial
    configs = [
        ('off', 20, 42),
        ('off', 20, 7),
        ('on', 20, 42),
        ('on', 20, 7),
    ]

    out = EXP_DIR / 'results' / '_article_probes.jsonl'
    print(f'Capturing probe answers for {len(configs)} trials...\n')

    with out.open('w', encoding='utf-8') as f:
        for comp, turn, seed in configs:
            print(f'[{comp}] turn={turn} seed={seed} ...', flush=True)
            t0 = time.time()
            messages, events, total_tokens = simulate_conversation(
                client, turn, comp, seed
            )
            probe_answer = ask_probe(client, messages)
            seen = MODULE_ORDER[:turn]
            score, recall = judge(client, probe_answer, seen)
            snr, useful, noise = compute_snr(messages)
            record = {
                'compression': comp,
                'observation_turn': turn,
                'seed': seed,
                'probe_answer': probe_answer,
                'quality_score': score,
                'recall_accuracy': recall,
                'total_tokens': total_tokens,
                'compression_events': events,
                'snr': snr,
                'useful_chars': useful,
                'noise_chars': noise,
                'wall_seconds': time.time() - t0,
            }
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
            f.flush()
            print(f'  quality={score} recall={recall} wall={time.time()-t0:.1f}s')
            print(f'  answer preview: {probe_answer[:180].replace(chr(10), " ")}...')
            print()

    print(f'写入 {out}')


if __name__ == '__main__':
    main()
