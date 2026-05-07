"""
eval_runner.py
===============
工具描述质量评测器。

核心流程：
  1. 加载 golden_set.jsonl（100条任务）
  2. 对每条任务，用指定版本（v1/v2）的工具描述跑 Agent
  3. 通过 pre_tool hook 捕获并拦截 Agent 的第一次 tool call
     （只捕获决策，不真正执行工具，节省API成本并避免副作用）
  4. 按 expected_tool / forbidden_tools / expected_args 打分
  5. 聚合指标并输出 JSON

用法:
    # 跑 v1（当前描述）
    python eval_runner.py --version v1 --out results_v1.json

    # 跑 v2（优化描述）
    python eval_runner.py --version v2 --out results_v2.json

    # 调试：只跑前5条
    python eval_runner.py --version v1 --out smoke.json --limit 5

    # 快速跑：只用1个seed
    python eval_runner.py --version v1 --out results_v1.json --seeds 1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 把仓库根目录加入 import 路径（本文件位于 experiments/ch04/exp1_tool_description_eval/ 下，上溯三层）
_REPO_ROOT = Path(__file__).resolve().parents[3]

# 自动加载根目录 .env，避免在子目录运行时找不到 API key
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

# API key / base_url 命名兼容：按 DEEPSEEK → HARNESS → OPENAI 优先级取首个非空值，
# 回填到 DEEPSEEK_API_KEY，让下游硬编码的 os.environ['DEEPSEEK_API_KEY'] 继续可用。
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

# 隔离 CLAUDE.md：只加载 eval_sandbox/CLAUDE.md（若存在），不向上遍历。
# 防止被 harness-py-book/CLAUDE.md 污染 Agent 的 system prompt。
import harness_py_pro.prompt as _prompt_mod  # noqa: E402


def _isolated_discover(cwd):
    cwd = Path(cwd) if not isinstance(cwd, Path) else cwd
    candidate = cwd.resolve() / 'CLAUDE.md'
    if candidate.exists():
        try:
            return [('CLAUDE.md', candidate.read_text(encoding='utf-8'))]
        except Exception:
            return []
    return []


_prompt_mod.discover_claude_md = _isolated_discover

# --prompt-version v2 启用升级版 system prompt（prompt_v2_template.py）
# 在所有参数解析前通过 sys.argv 预检测，因为 prompt 替换必须在 engine.run()
# 导入之前完成。
if '--prompt-version' in sys.argv:
    _idx = sys.argv.index('--prompt-version')
    if _idx + 1 < len(sys.argv) and sys.argv[_idx + 1] == 'v2':
        sys.path.insert(0, str(Path(__file__).parent))
        from prompt_v2_template import build_system_prompt_v2
        _prompt_mod.build_system_prompt = build_system_prompt_v2
        print('[eval_runner] 已启用 V2 system prompt（prompt_v2_template.py）')

from harness_py_pro import run, ModelConfig, AgentConfig  # noqa: E402
from harness_py_pro.tools import (  # noqa: E402
    create_default_registry, ToolRegistry, BaseTool,
)

# descriptions.py 在同一目录
sys.path.insert(0, str(Path(__file__).parent))
from descriptions import apply_descriptions  # noqa: E402


# 安全上限：单次任务最多捕获多少次工具调用（防Agent跑飞）
MAX_CAPTURES_PER_TASK = 5


class CaptureOnlyTool(BaseTool):
    """
    工具包装器：捕获 Agent 的调用，但只对"破坏性"工具返回假结果。

    设计理由：
      - 旧方案用 pre_tool hook 拦截所有工具，Agent 把 [HOOK拦截] 当作失败，
        触发 **假recovery**（重试不同工具），污染 any_call 指标。
      - 新方案对只读工具（read/grep/glob）**真实执行**，让 Agent 拿到
        真实内容以便生成后续工具调用的合理参数；
        对写入/执行类（write/edit/bash）返回"(simulated)"假成功，
        让 Agent 正常完成工作流而不产生副作用。

    这样得到的 all_calls 是 Agent 在"所有工具都正常工作"前提下的
    真实决策序列，更贴近生产环境。
    """

    def __init__(self, real_tool: BaseTool, captured: list[dict]):
        self.real = real_tool
        self.captured = captured
        self.name = real_tool.name
        self.read_only = real_tool.read_only

    def get_schema(self) -> dict:
        return self.real.get_schema()

    def execute(self, args: dict, config: AgentConfig) -> tuple[bool, str]:
        if len(self.captured) >= MAX_CAPTURES_PER_TASK:
            return False, '(eval) max captures per task reached'

        self.captured.append({'name': self.name, 'args': dict(args)})

        if self.read_only:
            # 只读工具实际执行：fixtures 就是为此准备的
            try:
                return self.real.execute(args, config)
            except Exception as e:
                return False, f'(simulated exec error) {e}'

        # 破坏性工具：返回假成功，不真正写盘/执行命令
        if self.name == 'write_file':
            path = args.get('path', '<unknown>')
            size = len(args.get('content', ''))
            return True, f'(simulated) Created {path} with {size} chars.'
        if self.name == 'edit_file':
            path = args.get('path', '<unknown>')
            return True, f'(simulated) Applied edit to {path}.'
        if self.name == 'bash':
            cmd = args.get('command', '')[:80]
            return True, f'(simulated) Command executed successfully: {cmd}'
        return True, '(simulated) ok'


def build_capture_registry(version: str, captured: list[dict]) -> ToolRegistry:
    """构建一个所有工具都被 CaptureOnlyTool 包装的 registry。"""
    real_registry = create_default_registry()
    apply_descriptions(real_registry, version)

    wrapped = ToolRegistry()
    for tool in real_registry.list_tools():
        wrapped.register(CaptureOnlyTool(tool, captured))
    return wrapped


def run_single_case(case: dict, version: str, seed: int, cwd: Path,
                    max_iter: int) -> dict:
    """跑一条任务，捕获 Agent 在无干扰下的完整工具调用序列。"""
    captured: list[dict] = []
    registry = build_capture_registry(version, captured)

    status = 'ok'
    error = ''

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
                cwd=cwd,
                max_iterations=max_iter,
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

    first_call = captured[0] if captured else None
    return {
        'id': case['id'],
        'version': version,
        'seed': seed,
        'category': case.get('category', ''),
        'expected_tool': case.get('expected_tool'),
        'first_call': first_call,
        'all_calls': captured,
        'status': status,
        'error': error,
    }


def score_case(case: dict, obs: dict) -> dict:
    """
    对一条观测打分（双轨指标）：
      - selected_right / first_call_right: 首次 tool call 即命中 → 描述质量
      - any_call_right:                    任意一次 call 命中     → Agent能力（含先读后改）
      - forbidden_hit:                     首次即误调禁用工具     → 描述缺少反向约束
      - args_ok:                           首次命中时参数正确     → 描述参数说明充分
    """
    first = obs['first_call']
    all_calls = obs.get('all_calls', [])
    expected = case['expected_tool']
    forbidden = case.get('forbidden_tools', [])

    # selected_right / first_call_right
    if expected is None:
        selected_right = first is None
    else:
        selected_right = first is not None and first['name'] == expected

    # any_call_right
    if expected is None:
        any_call_right = len(all_calls) == 0
    else:
        any_call_right = any(c.get('name') == expected for c in all_calls)

    # forbidden_hit（只看首次）
    if first is None:
        forbidden_hit = False
    elif '*' in forbidden:
        forbidden_hit = True
    else:
        forbidden_hit = first['name'] in forbidden

    # args_ok（只在首次命中时检）
    args_ok = True
    if 'expected_args' in case and first is not None:
        for k, v in case['expected_args'].items():
            if first.get('args', {}).get(k) != v:
                args_ok = False
                break

    return {
        'selected_right': selected_right,
        'any_call_right': any_call_right,
        'forbidden_hit': forbidden_hit,
        'args_ok': args_ok,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', choices=['v1', 'v2'], required=True,
                        help='使用的工具描述版本')
    parser.add_argument('--out', type=Path, required=True,
                        help='输出 JSON 路径')
    parser.add_argument('--seeds', type=int, default=3,
                        help='每条任务跑几个seed，默认3')
    parser.add_argument('--limit', type=int, default=None,
                        help='只跑前N条任务（调试用）')
    parser.add_argument('--sleep', type=float, default=0.3,
                        help='每次调用间隔秒数，默认0.3避免rate limit')
    parser.add_argument('--max-iterations', type=int, default=3,
                        help='Agent 单任务最大轮数，默认3（允许读-改工作流）')
    parser.add_argument('--prompt-version', choices=['v1', 'v2'], default='v1',
                        help='系统提示词版本：v1=当前4行最小版（默认），v2=prompt_v2_template.py')
    args = parser.parse_args()

    if not os.environ.get('DEEPSEEK_API_KEY'):
        print('[错误] 未设置 API key。请在 .env 中配置以下任意一个：')
        print('  DEEPSEEK_API_KEY / HARNESS_API_KEY / OPENAI_API_KEY')
        sys.exit(1)

    gs_path = Path(__file__).parent / 'golden_set.jsonl'
    cases = [
        json.loads(line)
        for line in gs_path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]
    if args.limit:
        cases = cases[:args.limit]

    sandbox = Path(__file__).parent / 'eval_sandbox'
    if not sandbox.exists():
        print(f'[错误] {sandbox} 不存在')
        print('  先运行：python prepare_fixtures.py')
        sys.exit(1)

    seeds = list(range(42, 42 + args.seeds))
    total = len(cases) * len(seeds)
    done = 0
    start = time.time()

    print(f'=== Tool Description Eval (version={args.version}) ===')
    print(f'  任务数: {len(cases)}, seeds: {seeds}, 总观测: {total}')
    print(f'  沙箱:   {sandbox}')
    print(f'  输出:   {args.out}')
    print()

    results = []
    for case in cases:
        for seed in seeds:
            obs = run_single_case(case, args.version, seed, sandbox,
                                  max_iter=args.max_iterations)
            scored = score_case(case, obs)
            obs.update(scored)
            results.append(obs)
            done += 1

            elapsed = time.time() - start
            eta = (total - done) * (elapsed / done) if done > 0 else 0
            got = obs['first_call']['name'] if obs['first_call'] else '<no_call>'
            want = case.get('expected_tool') or '<no_call>'
            # 标注三种状态：FC = first_call命中；AC = any_call命中；FAIL = 都没中
            if scored['selected_right']:
                mark = '  FC'
            elif scored['any_call_right']:
                mark = '  AC'
            else:
                mark = 'FAIL'
            ncalls = len(obs['all_calls'])
            print(
                f'[{done:3d}/{total}] {case["id"]:6s} seed={seed} '
                f'want={want:13s} got={got:13s} n={ncalls} {mark}  ETA {eta:5.0f}s'
            )
            time.sleep(args.sleep)

    # 汇总指标
    n = len(results)
    first_call_right = sum(1 for r in results if r['selected_right'])
    any_call_right = sum(1 for r in results if r['any_call_right'])
    forbidden_hit = sum(1 for r in results if r['forbidden_hit'])
    args_ok = sum(1 for r in results if r['args_ok'])
    errors = sum(1 for r in results if r['status'] == 'error')
    avg_calls = sum(len(r['all_calls']) for r in results) / n if n else 0.0

    summary = {
        'version': args.version,
        'prompt_version': args.prompt_version,  # 新增：记录用的system prompt版本
        'seeds': seeds,
        'num_cases': len(cases),
        'num_observations': n,
        'max_iterations': args.max_iterations,
        'framework': 'capture_only_v2',  # 标识所用评测框架
        'tool_selection_accuracy': first_call_right / n,
        'first_call_accuracy': first_call_right / n,
        'any_call_accuracy': any_call_right / n,
        'forbidden_hit_rate': forbidden_hit / n,
        'args_correctness': args_ok / n,
        'error_rate': errors / n,
        'avg_calls_per_task': avg_calls,
    }

    args.out.write_text(
        json.dumps({'summary': summary, 'results': results}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print()
    print(f'=== 总览 (version={args.version}) ===')
    print(f'  First-call Accuracy:  {first_call_right/n:.1%}  ({first_call_right}/{n})  ← 描述质量')
    print(f'  Any-call Accuracy:    {any_call_right/n:.1%}  ({any_call_right}/{n})  ← 含Agent工作流')
    print(f'  Forbidden Hit Rate:   {forbidden_hit/n:.1%}  ({forbidden_hit}/{n})')
    print(f'  Args Correctness:     {args_ok/n:.1%}  ({args_ok}/{n})')
    print(f'  Avg Calls per Task:   {avg_calls:.2f}')
    if errors:
        print(f'  [警告] 错误观测:     {errors/n:.1%}  ({errors}/{n})')
    print(f'  用时:                 {time.time()-start:.0f}s')
    print(f'  结果文件:             {args.out}')


if __name__ == '__main__':
    main()
