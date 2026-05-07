"""
实验二：四级压缩的触发频率与 Token 控制
==========================================
对应书稿 6.2 和 6.3。

用脚本化任务轨迹（避免 Agent 自主决策的方差）驱动 30 轮对话，
在每轮后调用 Compressor.compress 并统计各级触发次数。
产出触发频次矩阵 + token 曲线 + 摘要比例。

用法：
    python run.py --smoke
    python run.py
    python run.py --preserve 4 --threshold 0.80 --seeds 42
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

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

EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)


# ============ 观测器 ============
class InstrumentedCompressor(Compressor):
    """在原 Compressor 上加计数器。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.micro_count = 0
        self.snip_count = 0
        self.compact_count = 0
        self.reactive_count = 0
        # 摘要比例样本
        self.summary_ratios: list[float] = []
        # 每次压缩前后 token 变化
        self.compress_deltas: list[tuple[int, int]] = []

    def _microcompact(self, messages, preserve):
        before = sum(len(str(m.get('content', ''))) for m in messages)
        result = super()._microcompact(messages, preserve)
        after = sum(len(str(m.get('content', ''))) for m in result)
        if after < before:
            self.micro_count += 1
        return result

    def _snip(self, messages, preserve):
        before = sum(len(str(m.get('content', ''))) for m in messages)
        result = super()._snip(messages, preserve)
        after = sum(len(str(m.get('content', ''))) for m in result)
        if after < before:
            self.snip_count += 1
        return result

    def _compact(self, messages, preserve, llm_call):
        # 计算被压缩的候选集大小
        prefix = [messages[0]] if messages and messages[0].get('role') == 'system' else []
        tail = messages[-preserve * 2:] if preserve > 0 else []
        prefix_count = len(prefix)
        candidates = messages[prefix_count:len(messages) - len(tail)] if tail else messages[prefix_count:]
        candidate_chars = sum(len(str(m.get('content', ''))) for m in candidates)

        result = super()._compact(messages, preserve, llm_call)
        # 识别新的 compact 摘要消息
        if result is not messages:
            self.compact_count += 1
            # 找到摘要消息（内容含 system-reminder 且包含 "compacted"）
            for m in result[prefix_count:prefix_count + 1]:
                content = str(m.get('content', ''))
                if 'compacted' in content.lower():
                    summary_chars = len(content)
                    if candidate_chars > 0:
                        self.summary_ratios.append(summary_chars / candidate_chars)
                    break
        return result

    def compress(self, messages, target_tokens, *, llm_call=None, reactive=False):
        before_tokens = self.total_tokens(messages)
        if reactive:
            self.reactive_count += 1
        result = super().compress(messages, target_tokens, llm_call=llm_call, reactive=reactive)
        after_tokens = self.total_tokens(result)
        self.compress_deltas.append((before_tokens, after_tokens))
        return result


# ============ 任务脚本（贴近生产的混合负载）============
# 设计要点：
# 1. 150 步长会话（生产 Agent 的常见量级），Micro 会在后段逐渐耗尽截断目标
# 2. 工具尺寸混合：30%+ 步骤本身就 <500 字符（Micro 啃不动），30%+ 很小
#    Micro 帮助有限；只有中大型步骤给 Micro 发挥空间
# 3. Assistant 每轮产出 3-8K 字符的"思考段落"——这是 Snip 的主要目标
# 4. 文件名从有限池抽取 → 自然出现"重复读同一文件"的 Micro 疲劳场景
STEP_TYPES = [
    # (kind, (size_lo, size_hi), weight)
    ('grep',           (100,   400),   0.22),  # 极短，Micro 无法压缩
    ('ls',             (150,   500),   0.10),  # 极短
    ('bash_short',     (500,   1500),  0.13),  # 短，Micro 小幅受益
    ('bash_medium',    (2000,  6000),  0.18),  # 中
    ('read_file',      (5000,  15000), 0.20),  # 大
    ('pytest_verbose', (10000, 25000), 0.12),  # 非常大
    ('build_log',      (30000, 50000), 0.05),  # 超大
]
ASSISTANT_SIZE_RANGE = (3000, 8000)


def generate_task_script(seed: int, n_steps: int = 150) -> list[dict]:
    """
    按 STEP_TYPES 的权重采样 n_steps 步；文件从有限池抽取，产生重读模式。
    """
    rng = random.Random(seed)
    kinds = [t[0] for t in STEP_TYPES]
    ranges = [t[1] for t in STEP_TYPES]
    weights = [t[2] for t in STEP_TYPES]
    file_pool = [f'src/module_{i:02d}.py' for i in range(15)]
    test_pool = [f'tests/test_{i:02d}.py' for i in range(10)]
    script = []
    for i in range(n_steps):
        idx = rng.choices(range(len(STEP_TYPES)), weights=weights, k=1)[0]
        kind = kinds[idx]
        lo, hi = ranges[idx]
        size = rng.randint(lo, hi)
        pool = file_pool if 'read' in kind or 'grep' in kind else test_pool
        script.append({
            'step': i + 1,
            'kind': kind,
            'target': rng.choice(pool),
            'size_chars': size,
        })
    return script


def fake_tool_output(step: dict, rng: random.Random) -> str:
    """合成 tool 输出，内容长度按 step['size_chars'] 控制。"""
    size = step['size_chars']
    base = f'[{step["kind"]}] step {step["step"]} -> {step.get("target", "")}\n'
    filler = f'log line {rng.randint(1000, 9999)}\n'
    while len(base) < size:
        base += filler
    return base[:size]


# Assistant 推理段落的句子池。实际 Agent 每轮的"思考"就是这种风格的若干句拼接。
REASONING_FRAGMENTS = [
    'Looking at the output, I see the file contains the expected symbols.',
    'This confirms my hypothesis that the issue lies in the data layer.',
    'Before editing, I should verify the same pattern appears elsewhere in the codebase.',
    'The stack trace points to a race condition between the cache and the main loop.',
    'I need to cross-reference this against the test fixtures to make sure nothing breaks.',
    'Given the dependency graph I drew earlier, touching this file affects three callers.',
    'Let me draft the smallest change that addresses the root cause.',
    'I will run the tests after this edit and verify the regression does not recur.',
    'Reviewing the recent git history, a similar change was attempted but reverted.',
    'The type annotations show this function expects a list, but the caller passes a generator.',
    'If I touch this path I should also update the integration test that covers it.',
    'This edge case was not covered by the original spec; I will add a new test.',
    'The compressor threshold logic depends on microcompact_max_chars being small enough.',
    'I should not forget to update the README snippet to reflect the new API.',
    'Given the observed behavior, the next step is to add instrumentation and re-run.',
]


def fake_assistant_content(step: dict, rng: random.Random) -> str:
    """生成 3-8K 字符的推理段落，给 Snip 提供真实目标。"""
    lo, hi = ASSISTANT_SIZE_RANGE
    target_size = rng.randint(lo, hi)
    parts = [f'## Step {step["step"]} ({step["kind"]}) analysis\n']
    while sum(len(p) for p in parts) < target_size:
        parts.append(rng.choice(REASONING_FRAGMENTS))
        parts.append(' ')
    return ''.join(parts)[:target_size]


USER_PROMPTS = [
    '继续下一步。', '根据上面的结果，做下一步。', '按计划继续。',
    '分析这个输出并说下一步做什么。', '好，继续。',
]


# ============ 单次运行 ============
@dataclass
class RunRecord:
    preserve: int
    threshold: float
    seed: int
    n_steps: int = 0
    micro_count: int = 0
    snip_count: int = 0
    compact_count: int = 0
    reactive_count: int = 0
    api_errors: int = 0
    total_llm_calls: int = 0
    token_curve: list[int] = field(default_factory=list)
    summary_ratios: list[float] = field(default_factory=list)
    # 工作负载特征（事后核对）
    avg_tool_chars: float = 0.0
    assistant_chars_total: int = 0
    wall_seconds: float = 0.0


def run_single(
    client: LLMClient,
    preserve: int,
    threshold_pct: float,
    seed: int,
    n_steps: int = 150,
    use_llm_for_summary: bool = True,
) -> RunRecord:
    rng = random.Random(seed)
    compressor = InstrumentedCompressor(preserve_messages=preserve)
    messages = [{'role': 'system', 'content': 'You are a code analysis agent.'}]
    record = RunRecord(preserve=preserve, threshold=threshold_pct, seed=seed,
                       n_steps=n_steps)

    ctx_window = 128_000
    threshold = int(ctx_window * threshold_pct)
    script = generate_task_script(seed, n_steps)
    t0 = time.time()

    def llm_for_summary(prompt: str) -> str:
        if not use_llm_for_summary:
            return 'SUMMARY (stub): goals, done steps, in progress, files, next.'
        try:
            resp = client.complete([{'role': 'user', 'content': prompt}])
            record.total_llm_calls += 1
            return resp.get('content', '')
        except Exception:
            record.api_errors += 1
            return ''

    tool_char_total = 0
    assistant_char_total = 0

    for step in script:
        user_msg = rng.choice(USER_PROMPTS)
        messages.append({'role': 'user', 'content': user_msg})
        messages.append({
            'role': 'assistant',
            'content': '',
            'tool_calls': [{'id': f'call_{step["step"]}',
                            'type': 'function',
                            'function': {'name': step['kind'],
                                         'arguments': json.dumps({'step': step['step']})}}],
        })
        tool_body = fake_tool_output(step, rng)
        tool_char_total += len(tool_body)
        messages.append({
            'role': 'tool',
            'tool_call_id': f'call_{step["step"]}',
            'content': tool_body,
        })
        assistant_body = fake_assistant_content(step, rng)
        assistant_char_total += len(assistant_body)
        messages.append({
            'role': 'assistant',
            'content': assistant_body,
        })

        # 预检压缩
        current = compressor.total_tokens(messages)
        if current > threshold:
            messages = compressor.compress(messages, threshold, llm_call=llm_for_summary)
        record.token_curve.append(compressor.total_tokens(messages))

    record.micro_count = compressor.micro_count
    record.snip_count = compressor.snip_count
    record.compact_count = compressor.compact_count
    record.reactive_count = compressor.reactive_count
    record.summary_ratios = list(compressor.summary_ratios)
    record.avg_tool_chars = tool_char_total / n_steps if n_steps else 0.0
    record.assistant_chars_total = assistant_char_total
    record.wall_seconds = time.time() - t0
    return record


# ============ 入口 ============
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--preserve', type=int, nargs='+',
                    default=None, help='测试的 preserve_messages')
    ap.add_argument('--threshold', type=float, nargs='+',
                    default=None, help='测试的 threshold_pct')
    ap.add_argument('--seeds', type=int, nargs='+', default=None)
    ap.add_argument('--n-steps', type=int, default=None,
                    help='每个 trial 的对话步数（默认 smoke=60、full=150）')
    ap.add_argument('--no-llm-summary', action='store_true',
                    help='压缩阶段的摘要用 stub 代替，不真调 LLM')
    args = ap.parse_args()

    if args.smoke:
        preserves = args.preserve or [4]
        thresholds = args.threshold or [0.80]
        seeds = args.seeds or [42]
        n_steps = args.n_steps if args.n_steps is not None else 60
    else:
        # 网格收窄到 3×3×2=18，单次更长但整体时间可控
        preserves = args.preserve or [2, 4, 8]
        thresholds = args.threshold or [0.70, 0.80, 0.90]
        seeds = args.seeds or [42, 7]
        n_steps = args.n_steps if args.n_steps is not None else 150

    mc = ModelConfig.from_env()
    if not mc.api_key and not args.no_llm_summary:
        print('WARN: 未设置 API key，自动切换到 --no-llm-summary 模式。')
        args.no_llm_summary = True
    client = LLMClient(mc) if mc.api_key else None

    out = RESULTS / 'raw.jsonl'
    idx = 0
    total = len(preserves) * len(thresholds) * len(seeds)
    with out.open('w', encoding='utf-8') as f:
        for p in preserves:
            for th in thresholds:
                for s in seeds:
                    idx += 1
                    print(f'[{idx}/{total}] preserve={p} threshold={th} seed={s} n_steps={n_steps}')
                    record = run_single(client, p, th, s, n_steps=n_steps,
                                        use_llm_for_summary=not args.no_llm_summary)
                    print(f'    micro={record.micro_count} snip={record.snip_count} '
                          f'compact={record.compact_count} react={record.reactive_count} '
                          f'llm={record.total_llm_calls} wall={record.wall_seconds:.1f}s')
                    f.write(json.dumps(asdict(record), ensure_ascii=False) + '\n')
                    f.flush()

    print(f'\n原始数据已写入 {out}')


if __name__ == '__main__':
    main()
