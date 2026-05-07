"""
实验四：工具描述长度的效果拐点
==============================
对应书稿 4.6.7 "跨模型可迁移性与三层优化边界"。

只改变 bash 工具描述的长度（7 档），其他工具保持 V2，测 bash 相关任务准确率。
目标：验证或修正书稿中"DeepSeek-V3 的 512 字符效果拐点"论点。

用法:
    python run.py --smoke
    python run.py --length 400 --seeds 1
    python run.py                   # 全量 7档 × 23任务 × 3种子
"""
from __future__ import annotations

import argparse
import json
import os
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

# === API key / base_url 命名兼容 ===
# 仓库历史上出现过三种命名（DEEPSEEK_API_KEY / HARNESS_API_KEY / OPENAI_API_KEY），
# 按优先级取首个非空值回填 DEEPSEEK_API_KEY，让下游硬编码代码继续可用。
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

sys.path.insert(0, str(_REPO_ROOT))

# === 隔离 CLAUDE.md ===
import harness_py_pro.prompt as _prompt_mod  # noqa: E402


def _isolated_discover(cwd):
    cwd = Path(cwd) if not isinstance(cwd, Path) else cwd
    claude = cwd.resolve() / 'CLAUDE.md'
    if claude.exists():
        try:
            return [('CLAUDE.md', claude.read_text(encoding='utf-8'))]
        except Exception:
            return []
    return []


_prompt_mod.discover_claude_md = _isolated_discover

from harness_py_pro import run, ModelConfig, AgentConfig  # noqa: E402
from harness_py_pro.tools import (  # noqa: E402
    create_default_registry, ToolRegistry, BaseTool,
)

# 复用 exp1_tool_description_eval 的 V2 描述
_TOOL_EVAL_DIR = _REPO_ROOT / 'experiments' / 'ch04' / 'exp1_tool_description_eval'
sys.path.insert(0, str(_TOOL_EVAL_DIR))
from descriptions import V2_DESCRIPTIONS, apply_descriptions  # noqa: E402

EXP_DIR = Path(__file__).parent
RESULTS_DIR = EXP_DIR / 'results'
SANDBOX = _TOOL_EVAL_DIR / 'eval_sandbox'
GOLDEN_SET = _TOOL_EVAL_DIR / 'golden_set.jsonl'

# bash 描述的 8 档（结构骨架一致，tiktoken cl100k_base 实测 token 数为键）
# 详细 rationale 见 README.md 的 "Experimental Design" 节
sys.path.insert(0, str(EXP_DIR))
from _variants import VARIANTS as BASH_DESC_VARIANTS  # noqa: E402
_LEGACY_CHAR_VARIANTS = {
    20: 'Execute shell command.',
    50: 'Execute a shell command. Use for tests, git, packages.',
    100: (
        'Execute a shell command. Use for running tests, git, package managers. '
        'NEVER use for file operations.'
    ),
    200: (
        'Execute a shell command. Use ONLY for tasks without dedicated tools: '
        'tests (pytest), git (status, log), package managers (pip, npm), '
        'starting services. NEVER use for: cat/ls/find/grep/sed (use dedicated tools).'
    ),
    400: (
        'Execute a shell command. Use ONLY for tasks that have NO dedicated tool.\n'
        'VALID USE CASES:\n'
        '  - Running tests: pytest, jest, go test\n'
        '  - Git operations: git status, git log, git diff\n'
        '  - Package management: pip install, npm install\n'
        '  - Starting services: python main.py, npm run dev\n'
        'NEVER use bash for these — use the dedicated tool instead:\n'
        '  - cat / head / tail / less / more           -> read_file\n'
        '  - ls / find / dir / tree                    -> glob_search\n'
        '  - grep / rg / ack / ag                      -> grep_search\n'
        '  - sed / awk / echo > file                   -> edit_file or write_file\n'
        'When user literally types "cat X" or "ls *.py", TRANSLATE to the dedicated '
        'tool — do not execute it as bash.\n'
        'Args: command (required), timeout (seconds, default 120).'
    ),
    800: None,  # 由下面程序化构造
    1500: None,
}


def _build_variant_800() -> str:
    """V2 + 额外使用示例和边界说明，约 800 字符。"""
    base = BASH_DESC_VARIANTS[400]
    extra = (
        '\n\nDETAILED EXAMPLES:\n'
        '  - "Run the test suite" -> bash("pytest tests/ -v")\n'
        '  - "Check git status" -> bash("git status")\n'
        '  - "Install requests" -> bash("pip install requests")\n'
        '  - "Show last 3 commits" -> bash("git log --oneline -3")\n'
        'EDGE CASES:\n'
        '  - Long-running commands: set timeout param to avoid hanging\n'
        '  - Output >10K chars is truncated: pipe to head/tail in bash is OK for this\n'
        '  - Windows: Git Bash path required for Unix commands\n'
        'When in doubt, prefer the dedicated tool.'
    )
    return base + extra


def _build_variant_1500() -> str:
    """V2 + 大量冗余（约 1500 字符）。"""
    base = _build_variant_800()
    redundant = (
        '\n\nADDITIONAL GUIDANCE:\n'
        'The bash tool is powerful but also dangerous. It can execute any command '
        'that your shell can execute. Because of this power, we strongly recommend '
        'using dedicated tools whenever possible. Dedicated tools like read_file, '
        'glob_search, grep_search, edit_file, and write_file are safer because they '
        'have built-in permission checks, path validation, and encoding handling. '
        'When you use bash, you lose all of these protections. Furthermore, bash '
        'commands are hard to audit, hard to sandbox, and hard to reverse. '
        'If you find yourself reaching for bash to read a file, stop and use '
        'read_file instead. If you find yourself reaching for bash to find files, '
        'stop and use glob_search. If you find yourself reaching for bash to search '
        'content, stop and use grep_search. If you find yourself reaching for bash '
        'to modify a file, stop and use edit_file or write_file. The only legitimate '
        'uses of bash are running tests, executing git commands, managing packages, '
        'and starting services. Everything else should route through a dedicated tool.'
    )
    return base + redundant


# 老版 char-based variants 的代码（_build_variant_800 / _build_variant_1500
# 与 _LEGACY_CHAR_VARIANTS[20..400]）保留作为归档参考，不再被使用。
# 当前实验使用 _variants.py 的 8 档 token-indexed 版本。

LENGTHS = sorted(BASH_DESC_VARIANTS.keys())
SEEDS = [42, 43, 44]
MAX_CAPTURES_PER_TASK = 5

# 只跑 bash 相关的任务子集
RELEVANT_CATEGORIES = {
    'bash_positive',           # 8 条
    'glob_confuse_bash',       # 5 条
    'grep_confuse_bash',       # 5 条
    'read_confuse_bash',       # 5 条
}


# ============================================================
# Capture-only 包装
# ============================================================

class CaptureOnlyTool(BaseTool):
    def __init__(self, real_tool: BaseTool, captured: list):
        self.real = real_tool
        self.captured = captured
        self.name = real_tool.name
        self.read_only = real_tool.read_only

    def get_schema(self) -> dict:
        return self.real.get_schema()

    def execute(self, args, config):
        if len(self.captured) >= MAX_CAPTURES_PER_TASK:
            return False, '(eval) max captures per task reached'
        self.captured.append({'name': self.name, 'args': dict(args)})
        if self.real.read_only:
            try:
                return self.real.execute(args, config)
            except Exception as e:
                return False, f'(simulated exec error) {e}'
        if self.name == 'write_file':
            return True, f'(simulated) Created {args.get("path","?")}.'
        if self.name == 'edit_file':
            return True, f'(simulated) Applied edit to {args.get("path","?")}.'
        if self.name == 'bash':
            return True, f'(simulated) Command executed successfully.'
        return True, '(simulated) ok'


def build_registry_with_bash_length(desc_length: int, captured: list) -> ToolRegistry:
    """保持其他5个工具 V2 不变，只把 bash 描述换成指定长度的版本。"""
    real_registry = create_default_registry()
    apply_descriptions(real_registry, 'v2')

    # 特殊处理 bash
    bash_tool = real_registry.get('bash')
    if bash_tool is not None:
        new_desc = BASH_DESC_VARIANTS[desc_length]
        original_get_schema = bash_tool.get_schema

        def make_patched(orig, new_d):
            def patched():
                schema = orig()
                schema['description'] = new_d
                return schema
            return patched

        bash_tool.get_schema = make_patched(original_get_schema, new_desc)

    # Wrap all tools
    wrapped = ToolRegistry()
    for tool in real_registry.list_tools():
        wrapped.register(CaptureOnlyTool(tool, captured))
    return wrapped


def run_single(case: dict, desc_length: int, seed: int) -> dict:
    captured: list = []
    registry = build_registry_with_bash_length(desc_length, captured)

    status = 'ok'
    error = ''
    t_start = time.time()
    try:
        run(
            task=case['task'],
            model_config=ModelConfig(
                model='deepseek-chat',
                api_key=os.environ['DEEPSEEK_API_KEY'],
                base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
                context_window=64000,
                max_output_tokens=1024,
                temperature=0.0,
                seed=seed,
            ),
            agent_config=AgentConfig(
                cwd=SANDBOX,
                max_iterations=3,
                planning_turns=0,
                allow_write=True,
                allow_shell=True,
                sandbox_mode='bypass',
                network_isolated=False,
            ),
            tool_registry=registry,
            verbose=False,
        )
    except Exception as e:
        status = 'error'
        error = f'{type(e).__name__}: {e}'

    duration = time.time() - t_start

    first = captured[0] if captured else None
    expected = case.get('expected_tool')
    forbidden = case.get('forbidden_tools', [])

    if expected is None:
        first_call_right = first is None
    else:
        first_call_right = first is not None and first['name'] == expected

    if expected is None:
        any_call_right = len(captured) == 0
    else:
        any_call_right = any(c.get('name') == expected for c in captured)

    if first is None:
        forbidden_hit = False
    elif '*' in forbidden:
        forbidden_hit = True
    else:
        forbidden_hit = first['name'] in forbidden

    return {
        'id': case['id'],
        'category': case.get('category', ''),
        'bash_desc_length': desc_length,
        'seed': seed,
        'first_call': first,
        'all_calls': captured,
        'n_calls': len(captured),
        'first_call_right': first_call_right,
        'any_call_right': any_call_right,
        'forbidden_hit': forbidden_hit,
        'duration_sec': round(duration, 2),
        'status': status,
        'error': error,
    }


def load_existing_results(out_path: Path) -> tuple[list, set]:
    if not out_path.exists():
        return [], set()
    try:
        existing = json.loads(out_path.read_text(encoding='utf-8'))
        results = existing.get('results', [])
        done_keys = {(r['id'], r['bash_desc_length'], r['seed']) for r in results}
        return results, done_keys
    except Exception:
        return [], set()


def _save(out_path, lengths, seeds, num_cases, results):
    out_path.write_text(
        json.dumps({
            'summary': {
                'lengths': lengths,
                'seeds': seeds,
                'num_cases': num_cases,
                'num_observations': len(results),
            },
            'results': results,
        }, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _summarize(results, lengths, out_path):
    print()
    print(f'=== 汇总 (n={len(results)}) ===')
    print(f'{"tokens":6s} {"n":4s} {"FC%":6s} {"ΔFC/100t":10s} {"Forbid%":9s} '
          f'{"bash_pos%":10s} {"glob_conf%":11s} {"grep_conf%":11s} {"read_conf%":11s}')
    prev_fc = None
    prev_tokens = None
    for length in lengths:
        rs = [r for r in results if r['bash_desc_length'] == length]
        if not rs:
            continue
        n = len(rs)
        fc = sum(1 for r in rs if r['first_call_right']) / n
        fb = sum(1 for r in rs if r['forbidden_hit']) / n

        # 派生指标：相对于上一档每 100 tokens 的 FC 边际变化（pp）
        # 第一档无上一档参照，显示为 "—"
        if prev_fc is None:
            delta_str = '—'
        else:
            delta_tokens = length - prev_tokens
            delta_fc_pp = (fc - prev_fc) * 100  # percentage points
            per_100 = delta_fc_pp / (delta_tokens / 100) if delta_tokens else 0
            delta_str = f'{per_100:+.1f}pp'
        prev_fc = fc
        prev_tokens = length

        def cat_fc(cat):
            c = [r for r in rs if r['category'] == cat]
            if not c:
                return 0.0
            return sum(1 for r in c if r['first_call_right']) / len(c)
        print(f'{length:<6} {n:<4} {fc*100:5.1f}% {delta_str:<10} {fb*100:7.1f}% '
              f'{cat_fc("bash_positive")*100:8.1f}% '
              f'{cat_fc("glob_confuse_bash")*100:9.1f}% '
              f'{cat_fc("grep_confuse_bash")*100:9.1f}% '
              f'{cat_fc("read_confuse_bash")*100:9.1f}%')
    print(f'\n结果: {out_path}')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--length', type=int, default=None, choices=LENGTHS,
                        help='只跑某个长度档')
    parser.add_argument('--seeds', type=int, default=3)
    parser.add_argument('--sleep', type=float, default=0.3)
    parser.add_argument('--out', default='results.json')
    args = parser.parse_args()

    if not os.environ.get('DEEPSEEK_API_KEY'):
        print('[错误] 未设置 API key。请在 .env 中配置以下任意一个：')
        print('  DEEPSEEK_API_KEY / HARNESS_API_KEY / OPENAI_API_KEY')
        sys.exit(1)

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / args.out

    # 加载任务并过滤到 bash 相关
    all_cases = [json.loads(l) for l in GOLDEN_SET.read_text(encoding='utf-8').splitlines() if l.strip()]
    cases = [c for c in all_cases if c.get('category') in RELEVANT_CATEGORIES]
    print(f'[info] 筛选出 {len(cases)} 条 bash 相关任务')

    # 配置档位
    if args.smoke:
        # Smoke：跑 1 档（中间偏小），覆盖 4 类任务各 2 条，1 seed
        # 目的是验证框架 + token 数测量 + 4 类任务都能走通；不验证 curve 形状
        smoke_length = LENGTHS[len(LENGTHS) // 2 - 1]  # 中档偏小
        lengths = [smoke_length]
        by_cat: dict = {}
        for c in cases:
            by_cat.setdefault(c['category'], []).append(c)
        cases = []
        for cat, cs in by_cat.items():
            cases.extend(cs[:2])
        seeds = [42]
    elif args.length is not None:
        lengths = [args.length]
        seeds = list(range(42, 42 + args.seeds))
    else:
        lengths = LENGTHS
        seeds = list(range(42, 42 + args.seeds))

    results, done_keys = load_existing_results(out_path)
    total = len(lengths) * len(cases) * len(seeds)
    done = len(done_keys)

    print(f'=== Exp4 Description Length Curve ===')
    print(f'  Lengths: {lengths}')
    print(f'  Cases: {len(cases)} (bash 相关)')
    print(f'  Seeds: {seeds}')
    print(f'  Total: {total}, Done: {done}')
    print(f'  Token archetypes: {lengths}')
    print(f'  (chars: {[len(BASH_DESC_VARIANTS[l]) for l in lengths]})')
    print()

    start = time.time()
    for length in lengths:
        for case in cases:
            for seed in seeds:
                key = (case['id'], length, seed)
                if key in done_keys:
                    continue
                obs = run_single(case, length, seed)
                results.append(obs)
                done += 1
                mark = '  FC' if obs['first_call_right'] else ('  AC' if obs['any_call_right'] else 'FAIL')
                got = obs['first_call']['name'] if obs['first_call'] else '<no>'
                elapsed = time.time() - start
                print(f'[len={length:4d}] [{done:3d}/{total}] {case["id"]:6s} s={seed} '
                      f'want={case.get("expected_tool") or "<no>":13s} got={got:13s} {mark}  '
                      f'({elapsed:.0f}s)')
                _save(out_path, lengths, seeds, len(cases), results)
                time.sleep(args.sleep)

    _summarize(results, lengths, out_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
