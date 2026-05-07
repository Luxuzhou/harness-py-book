"""
实验二：Cache 前缀稳定性敏感度
=================================
在 DeepSeek 自动缓存机制下，测量 system prompt 不同程度的"污染"
对实测命中率的影响。

五种配置（按污染程度递增）：
- A 规范版：system prompt 完全静态，动态信息放 user message
- D 小时级时间戳：system prompt 开头嵌入"当前时间: YYYY-MM-DD HH:00"（小时内稳定）
- E schema 乱序：system prompt 静态，但每轮 tools 列表随机重排
- B 秒级时间戳：system prompt 开头嵌入"当前时间: YYYY-MM-DD HH:MM:SS"（每轮变）
- C Request-ID：system prompt 开头嵌入"Request-ID: <uuid4>"（每轮变）

每种配置跑 30 轮独立的"解释文件"小任务，读取 DeepSeek 返回的
`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` 计算每轮命中率。

用法：
    python run.py --smoke              # 2配置×3轮
    python run.py                      # 5配置×30轮 全量
    python run.py --configs A,B,C      # 只跑指定配置
    python run.py --rounds 15          # 改轮数
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

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
RESULTS_DIR = EXP_DIR / 'results'

# 稳定的 system prompt 基线（约 3500 字符 / 2000 tokens）
# 故意做得比较长，以保证缓存有足够的 token 量可以命中
_SYSTEM_BASE = """You are a code analysis assistant. Your job is to explain
the purpose and key responsibilities of individual Python files.

## Analysis protocol

1. Read the file path and content provided in the user message.
2. Identify the module's primary responsibility in one sentence.
3. List 2-4 key functions/classes with their roles.
4. Note any non-obvious design decisions or constraints.
5. Keep the response under 200 words.

## Output format

Always structure the response as:

**Purpose**: <one sentence>

**Key components**:
- `<name>`: <role>
- `<name>`: <role>
...

**Notes**: <any non-obvious design decisions, or "None" if none>

## Scope limits

- Do not invent code that isn't in the file.
- Do not speculate about files not shown.
- If the file is empty or unparseable, say so explicitly.
- Do not suggest refactorings unless the user asks for them.

## Communication style

- Use concise technical language. Avoid filler phrases.
- Refer to Python identifiers with backticks.
- Use markdown lists for enumerations.
- Never apologize or hedge unnecessarily.

## Task boundaries

You analyze one file per request. You do not:
- Run code or tools
- Modify files
- Create new files
- Access the network
- Interpret the user's intent beyond the explicit file-analysis request

## Error handling

If the user message does not contain a file path and content, respond:
"I need both a file path and the file's content to analyze it."

Do not ask clarifying questions in the initial response.

## Consistency requirement

Your response style must be stable across many requests. Given the same file
content twice, your response should be essentially the same. This consistency
is measured and affects evaluation.
"""

# 常见的 Python 源文件片段，用于轮次间交替
# 每个文件用一个小 snippet 作任务输入，减少输出差异
_FILE_SAMPLES = [
    ('config.py', 'import os\nfrom dataclasses import dataclass\n\n@dataclass\nclass Config:\n    debug: bool = False\n    port: int = 8080\n'),
    ('utils.py', 'def clamp(x: int, lo: int, hi: int) -> int:\n    return max(lo, min(hi, x))\n'),
    ('models.py', 'from pydantic import BaseModel\n\nclass User(BaseModel):\n    id: int\n    name: str\n    email: str | None = None\n'),
    ('logging.py', 'import logging\n\nlog = logging.getLogger(__name__)\n\ndef setup(level: str) -> None:\n    logging.basicConfig(level=level.upper())\n'),
    ('cache.py', 'from functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef fib(n: int) -> int:\n    return n if n < 2 else fib(n-1) + fib(n-2)\n'),
]

# 最小工具集（仅用于 E 配置的"乱序"测试；A/B/C/D 配置不传工具）
_TOOLS_ORIGINAL = [
    {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': 'Read a file from the workspace.',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
                'required': ['path'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'grep_search',
            'description': 'Search file contents using regex.',
            'parameters': {
                'type': 'object',
                'properties': {'pattern': {'type': 'string'}, 'path': {'type': 'string'}},
                'required': ['pattern'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'glob_search',
            'description': 'Find files by glob pattern.',
            'parameters': {
                'type': 'object',
                'properties': {'pattern': {'type': 'string'}},
                'required': ['pattern'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'write_file',
            'description': 'Write content to a file.',
            'parameters': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
                'required': ['path', 'content'],
            },
        },
    },
]


def build_system_prompt(config: str, round_idx: int) -> str:
    """根据配置构造 system prompt。"""
    now = datetime.now()
    if config == 'A':
        return _SYSTEM_BASE
    if config == 'B':
        ts = now.strftime('%Y-%m-%d %H:%M:%S')
        return f'Current time: {ts}\n\n' + _SYSTEM_BASE
    if config == 'C':
        return f'Request-ID: {uuid4()}\n\n' + _SYSTEM_BASE
    if config == 'D':
        ts = now.strftime('%Y-%m-%d %H:00')
        return f'Current time: {ts}\n\n' + _SYSTEM_BASE
    if config == 'E':
        # system prompt 保持静态，乱序在 tools 参数上处理
        return _SYSTEM_BASE
    raise ValueError(f'unknown config: {config}')


def build_tools(config: str, round_idx: int) -> list[dict] | None:
    """A/B/C/D 不传工具；E 每轮随机重排工具列表。"""
    if config != 'E':
        return None
    tools = list(_TOOLS_ORIGINAL)
    rng = random.Random(round_idx * 7919)  # 每轮不同的稳定打乱
    rng.shuffle(tools)
    return tools


def build_user_message(round_idx: int) -> str:
    """每轮用不同的文件分析任务。"""
    name, code = _FILE_SAMPLES[round_idx % len(_FILE_SAMPLES)]
    return f'Analyze this file.\n\nPath: `{name}`\n\nContent:\n```python\n{code}```'


def run_config(config: str, rounds: int, client: LLMClient, sleep_sec: float) -> list[dict]:
    """跑一个配置的完整轮次，返回每轮的指标。"""
    results = []
    for r in range(1, rounds + 1):
        system_prompt = build_system_prompt(config, r)
        user_msg = build_user_message(r)
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_msg},
        ]
        tools = build_tools(config, r)

        t0 = time.time()
        try:
            resp = client.complete(messages, tools)
            usage = resp.get('usage', {})
            err = None
        except Exception as exc:
            usage = {}
            err = f'{type(exc).__name__}: {exc}'
        duration = time.time() - t0

        # DeepSeek 字段：prompt_cache_hit_tokens / prompt_cache_miss_tokens
        hit = usage.get('prompt_cache_hit_tokens', 0)
        miss = usage.get('prompt_cache_miss_tokens', 0)
        prompt_total = usage.get('prompt_tokens', 0)
        completion = usage.get('completion_tokens', 0)
        # 有些时候 hit+miss ≠ prompt_tokens（包含 completion cache 或其他字段）
        cache_denominator = hit + miss
        hit_rate = (hit / cache_denominator * 100) if cache_denominator > 0 else 0.0

        metrics = {
            'config': config,
            'round': r,
            'prompt_tokens': prompt_total,
            'cache_hit_tokens': hit,
            'cache_miss_tokens': miss,
            'completion_tokens': completion,
            'hit_rate_pct': round(hit_rate, 2),
            'duration_sec': round(duration, 2),
            'error': err,
        }
        results.append(metrics)
        print(
            f'  [{config}][{r:>2}/{rounds}] '
            f'hit={hit:>5} miss={miss:>5} rate={hit_rate:>5.1f}% '
            f'prompt={prompt_total} completion={completion} '
            f'duration={duration:.1f}s'
            + (f' ERR={err}' if err else ''),
            flush=True,
        )
        if sleep_sec > 0:
            time.sleep(sleep_sec)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true', help='2配置×3轮')
    parser.add_argument('--configs', default='A,B,C,D,E')
    parser.add_argument('--rounds', type=int, default=30)
    parser.add_argument('--sleep', type=float, default=1.5)
    parser.add_argument('--out', default='results.json')
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)

    if args.smoke:
        configs = ['A', 'B']
        rounds = 3
    else:
        configs = [c.strip() for c in args.configs.split(',') if c.strip()]
        rounds = args.rounds

    mc = ModelConfig.from_env()
    if not mc.api_key:
        print('ERROR: 未设置 API key。请在 .env 中设置 HARNESS_API_KEY 或 OPENAI_API_KEY。')
        return 1
    mc.temperature = 0.0  # 最小化模型输出差异

    client = LLMClient(mc)
    out_path = RESULTS_DIR / args.out

    all_results: list[dict] = []
    t0 = time.time()
    for cfg in configs:
        print(f'\n=== 配置 {cfg} ({rounds}轮) ===')
        cfg_results = run_config(cfg, rounds, client, args.sleep)
        all_results.extend(cfg_results)
        # 增量写盘
        out_path.write_text(
            json.dumps(all_results, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

    elapsed = time.time() - t0
    print(f'\n完成 {len(configs)}×{rounds} = {len(all_results)} 次调用，用时 {elapsed:.0f}s')
    print(f'结果: {out_path}')

    # 简要汇总
    print('\n=== 各配置命中率均值（排除第1轮冷启动） ===')
    for cfg in configs:
        cfg_data = [r for r in all_results if r['config'] == cfg and r['round'] > 1]
        if not cfg_data:
            continue
        valid = [r for r in cfg_data if r.get('error') is None]
        if not valid:
            print(f'  {cfg}: 全部失败')
            continue
        mean_rate = sum(r['hit_rate_pct'] for r in valid) / len(valid)
        print(f'  {cfg}: 均值={mean_rate:.1f}% (n={len(valid)})')

    return 0


if __name__ == '__main__':
    sys.exit(main())
