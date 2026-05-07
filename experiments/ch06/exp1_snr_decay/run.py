"""
实验一：上下文信噪比塌陷
===========================
对应书稿 6.1.1。测量在 10-20 轮代码分析任务中，上下文信噪比随轮次的变化，
以及 Harness-py 压缩是否能稳定 SNR。

设计：
  自变量：compression (off/on) × observation_turn (3/6/10/15/20)
  因变量：snr、total_tokens、quality_score、recall_accuracy
  样本：
    --smoke: 2 seeds × {3, 10} = 8 次运行（仅 compression=off 做对照）
    full:    3 seeds × {3, 6, 10, 15, 20} × {off, on} = 30 次运行

用法：
    python run.py --smoke
    python run.py
    python run.py --no-judge           # 跳过 quality_score，只测结构指标
    python run.py --seeds 42 7 123
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# ============ 环境加载 ============
_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, str(_REPO_ROOT))

from harness_py.compressor import Compressor  # noqa: E402
from harness_py.http_client import LLMClient  # noqa: E402
from harness_py.config import ModelConfig  # noqa: E402

# ============ 目录 ============
EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures' / 'modules'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)

# ============ 度量指标 ============
@dataclass
class Metrics:
    compression: str          # 'off' | 'on'
    observation_turn: int
    seed: int
    snr: float                # useful / total
    useful_chars: int
    noise_chars: int
    total_tokens: int
    quality_score: float      # 0-5，-1 表示未评
    recall_accuracy: int      # 0-10，-1 表示未评
    wall_seconds: float
    compression_events: int   # 触发的压缩次数


def compute_snr(messages: list[dict]) -> tuple[float, int, int]:
    """有用字符 / 总字符。有用 = user + assistant；噪声 = tool。"""
    useful = 0
    noise = 0
    for m in messages:
        content = m.get('content') or ''
        role = m.get('role')
        n = len(content) if isinstance(content, str) else len(str(content))
        if role == 'tool':
            noise += n
        elif role in ('user', 'assistant'):
            useful += n
    total = useful + noise
    return (useful / total if total else 1.0, useful, noise)


# ============ 任务生成 ============
def build_system_prompt() -> str:
    return (
        '你是一个代码阅读助手。用户会依次给你若干 Python 模块的路径，'
        '你需要读取内容后用 2-3 句话总结模块的核心功能。'
        '不要展开讨论，只输出总结。'
    )


def read_module(name: str) -> str:
    """读取一个 fixture 模块的源码。"""
    path = FIXTURES / f'{name}.py'
    if not path.exists():
        return f'# 模块 {name} 不存在（fixture 缺失）'
    return path.read_text(encoding='utf-8')


MODULE_ORDER = [
    'auth_service', 'user_repository', 'email_sender', 'audit_logger',
    'rate_limiter', 'cache_client', 'config_loader', 'job_queue',
    'metrics_reporter', 'health_checker',
    # 超过 10 的部分用来跑 turn=15, 20 的观察
    'session_store', 'billing_calculator', 'pdf_renderer',
    'feature_flags', 'webhook_dispatcher', 'scheduler',
    'template_engine', 'data_validator', 'csv_exporter', 'search_indexer',
]


READ_MODULE_TOOL_SCHEMA = {
    'type': 'function',
    'function': {
        'name': 'read_module',
        'description': '读取指定模块的源码内容',
        'parameters': {
            'type': 'object',
            'properties': {
                'module': {'type': 'string', 'description': '模块名（不含 .py）'},
            },
            'required': ['module'],
        },
    },
}


def append_turn_messages(messages: list[dict], module_name: str, turn_idx: int) -> None:
    """
    把一轮合法的交互追加到 messages：
      user → assistant(tool_calls) → tool(result)
    之后调用方负责再调 LLM 生成总结并追加到 messages。

    原版直接往 messages 塞孤立的 tool 消息（role='tool' 但前置 assistant 无 tool_calls 指向），
    违反 OpenAI/DeepSeek 协议，后续 probe/judge 调用会触发 HTTP 400。此修法把 tool
    严格配对到前置 assistant.tool_calls。
    """
    call_id = f'call_{turn_idx}_{module_name}'
    messages.append({
        'role': 'user',
        'content': f'请读取 {module_name}.py 并用 2-3 句话总结其核心功能。',
    })
    messages.append({
        'role': 'assistant',
        'content': '',
        'tool_calls': [{
            'id': call_id,
            'type': 'function',
            'function': {
                'name': 'read_module',
                'arguments': json.dumps({'module': module_name}, ensure_ascii=False),
            },
        }],
    })
    messages.append({
        'role': 'tool',
        'tool_call_id': call_id,
        'content': read_module(module_name),
    })


# ============ 主循环 ============
def simulate_conversation(
    client: LLMClient,
    target_turn: int,
    compression: str,
    seed: int,
) -> tuple[list[dict], int, int]:
    """
    跑一个 target_turn 轮的对话，返回最终 messages、压缩次数、总 token。
    compression='off' 时 Compressor 不介入；'on' 时在 70% 阈值触发。

    每轮的消息流严格按 OpenAI 协议：
      user(请求) → assistant(发起 tool_call) → tool(返回文件内容) → assistant(总结)
    LLM 在看到 tool 返回后会生成总结。
    """
    import random
    random.seed(seed)

    compressor = Compressor(preserve_messages=4)
    messages: list[dict] = [
        {'role': 'system', 'content': build_system_prompt()}
    ]
    compression_events = 0

    ctx_window = 6_000
    threshold = int(ctx_window * 0.70)

    for t in range(1, target_turn + 1):
        mod = MODULE_ORDER[(t - 1) % len(MODULE_ORDER)]
        # 追加合法的 user + assistant(tool_calls) + tool(result) 三消息
        append_turn_messages(messages, mod, t)

        # 让 LLM 基于 tool 返回生成总结
        try:
            resp = client.complete(messages, tools=[READ_MODULE_TOOL_SCHEMA])
            assistant_content = resp.get('content', '(空)')
        except Exception as exc:
            assistant_content = f'(LLM 错误: {exc})'
        messages.append({'role': 'assistant', 'content': assistant_content})

        # 压缩判定
        if compression == 'on':
            current = compressor.total_tokens(messages)
            if current > threshold:
                def _llm(prompt: str) -> str:
                    r = client.complete([{'role': 'user', 'content': prompt}])
                    return r.get('content', '')
                messages = compressor.compress(messages, threshold, llm_call=_llm)
                compression_events += 1

    total_tokens = compressor.total_tokens(messages)
    return messages, compression_events, total_tokens


# ============ 综合问题评估 ============
PROBE_QUESTION = (
    '基于你已经看过的所有模块，回答下列问题：'
    '1) 哪些模块之间有明显的依赖关系（例如 A 调用 B）？'
    '2) 列出你看到过的所有日志或审计相关的模块名。'
    '3) 如果要实现一个"用户注册"流程，会用到哪几个模块？'
    '请严格基于之前看过的内容作答，不要编造模块名。'
)


def ask_probe(client: LLMClient, messages: list[dict]) -> str:
    probe = list(messages) + [{'role': 'user', 'content': PROBE_QUESTION}]
    try:
        resp = client.complete(probe)
        return resp.get('content', '')
    except Exception as exc:
        return f'(probe 调用失败: {exc})'


JUDGE_PROMPT = """你是一个评分员。下面是 Agent 看过若干代码模块后对综合问题的回答。
请基于下列事实评分：
- 真实存在的模块名集合：{real_modules}
- 审计/日志相关模块：audit_logger, metrics_reporter
- 涉及"用户注册"的合理组合应至少包含：auth_service, user_repository, 以及
  email_sender（发验证邮件）或 audit_logger（记录注册事件）中至少一个

评分标准（1-5 分）：
1 = 大量编造模块名或完全答非所问
2 = 回答结构正确但大部分信息错误
3 = 部分正确，有少量编造
4 = 基本准确，仅有语义模糊
5 = 准确且引用真实模块，关系判断合理

Agent 的回答：
---
{answer}
---

只输出一行：`score=<数字>, recall=<0-10的整数>`。
recall 是回答中正确引用的真实模块数量（去重）。"""


def judge(client: LLMClient, answer: str, seen_modules: list[str]) -> tuple[float, int]:
    prompt = JUDGE_PROMPT.format(
        real_modules=', '.join(seen_modules),
        answer=answer[:3000],  # 截断避免 judge 窗口溢出
    )
    try:
        resp = client.complete([{'role': 'user', 'content': prompt}])
        text = resp.get('content', '')
    except Exception:
        return (-1.0, -1)
    score, recall = -1.0, -1
    for token in text.replace(',', ' ').split():
        if token.startswith('score='):
            try:
                score = float(token.split('=', 1)[1])
            except ValueError:
                pass
        if token.startswith('recall='):
            try:
                recall = int(token.split('=', 1)[1])
            except ValueError:
                pass
    return (score, recall)


# ============ 单次运行 ============
def run_single(
    client: LLMClient,
    compression: str,
    observation_turn: int,
    seed: int,
    skip_judge: bool,
) -> Metrics:
    t0 = time.time()
    messages, events, total_tokens = simulate_conversation(
        client, observation_turn, compression, seed
    )
    snr, useful_chars, noise_chars = compute_snr(messages)

    quality, recall = -1.0, -1
    if not skip_judge:
        answer = ask_probe(client, messages)
        seen = MODULE_ORDER[:observation_turn]
        quality, recall = judge(client, answer, seen)

    return Metrics(
        compression=compression,
        observation_turn=observation_turn,
        seed=seed,
        snr=snr,
        useful_chars=useful_chars,
        noise_chars=noise_chars,
        total_tokens=total_tokens,
        quality_score=quality,
        recall_accuracy=recall,
        wall_seconds=time.time() - t0,
        compression_events=events,
    )


# ============ 入口 ============
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', action='store_true',
                    help='最小规模，仅跑 off × {3, 10} × 2 seeds')
    ap.add_argument('--no-judge', action='store_true',
                    help='跳过 LLM-as-judge，只测 SNR/token 结构指标')
    ap.add_argument('--seeds', type=int, nargs='+', default=None)
    ap.add_argument('--turns', type=int, nargs='+', default=None)
    ap.add_argument('--compression', choices=['off', 'on', 'both'], default='both')
    args = ap.parse_args()

    if args.smoke:
        seeds = args.seeds or [42, 7]
        turns = args.turns or [3, 10]
        compressions = ['off']
    else:
        seeds = args.seeds or [42, 7, 123]
        turns = args.turns or [3, 6, 10, 15, 20]
        compressions = ['off', 'on'] if args.compression == 'both' else [args.compression]

    mc = ModelConfig.from_env()
    if not mc.api_key:
        print('ERROR: 未设置 HARNESS_API_KEY')
        sys.exit(2)
    # 让 seeds 产生真实方差（LLMClient 不转发 seed 到 API，温度>0 才有采样随机性）
    mc.temperature = 0.3
    client = LLMClient(mc)

    out_path = RESULTS / 'raw.jsonl'
    with out_path.open('w', encoding='utf-8') as f:
        idx = 0
        total = len(seeds) * len(turns) * len(compressions)
        for comp in compressions:
            for turn in turns:
                for seed in seeds:
                    idx += 1
                    print(f'[{idx}/{total}] compression={comp} turn={turn} seed={seed}')
                    m = run_single(client, comp, turn, seed, args.no_judge)
                    f.write(json.dumps(asdict(m), ensure_ascii=False) + '\n')
                    f.flush()

    print(f'\n原始数据已写入 {out_path}')
    print('运行 plot.py 生成聚合表和图表。')


if __name__ == '__main__':
    main()
