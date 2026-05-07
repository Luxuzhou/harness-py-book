"""
实验二：工具集规模对选择准确率的影响
======================================
对应书稿 4.4.3 "为何少量工具优于大而全的工具集"。

在 DeepSeek-V3 + harness-py-pro 上测量：给 Agent 暴露 3/6/12/24/48 个
工具时，First-call Accuracy / Avg Calls / Token 消耗如何变化。

实验设定：
  - 复用 exp1_tool_description_eval/ 的 100 条 Golden Set 和 capture-only framework
  - 真实工具 = V2 描述的 6 个内置工具
  - 填充工具 = noop_1 ... noop_42（结构类似但调用必失败）
  - 工具档位：3 / 6 / 12 / 24 / 48

用法:
    python run.py --smoke             # 1 档 × 5 任务 × 1 种子
    python run.py --tool-count 12 --seeds 1
    python run.py                     # 全量 5 × 100 × 3 = 1500 次
"""
from __future__ import annotations

import argparse
import json
import os
import random
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
# 本实验原先硬编码 DEEPSEEK_API_KEY 会让仅配了 OPENAI_API_KEY 的读者直接崩。
# 按优先级取首个非空值，回填 DEEPSEEK_API_KEY，下游直接用 os.environ['DEEPSEEK_API_KEY'] 的代码不用改。
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

# === 隔离 CLAUDE.md 发现，避免仓库 CLAUDE.md 污染 ===
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

# 复用 exp1_tool_description_eval 的 V2 描述和 capture 框架
_TOOL_EVAL_DIR = _REPO_ROOT / 'experiments' / 'ch04' / 'exp1_tool_description_eval'
sys.path.insert(0, str(_TOOL_EVAL_DIR))
from descriptions import apply_descriptions  # noqa: E402

EXP_DIR = Path(__file__).parent
RESULTS_DIR = EXP_DIR / 'results'
SANDBOX = _TOOL_EVAL_DIR / 'eval_sandbox'
GOLDEN_SET = _TOOL_EVAL_DIR / 'golden_set.jsonl'

TOOL_COUNTS = [3, 6, 12, 24, 48]
SEEDS = [42, 43, 44]
MAX_CAPTURES_PER_TASK = 5


# ============================================================
# Noop 工具：结构类似真实工具但不做实事
# ============================================================

NOOP_TEMPLATES = [
    # (name, description, params)
    ('search_docs', 'Search documentation by keyword.', {'query': 'string'}),
    ('fetch_url', 'Fetch content from a URL.', {'url': 'string'}),
    ('run_linter', 'Run code linter on a file.', {'path': 'string'}),
    ('format_code', 'Format code file according to project style.', {'path': 'string'}),
    ('list_branches', 'List git branches in the repo.', {}),
    ('get_env', 'Get environment variable value.', {'name': 'string'}),
    ('hash_file', 'Compute SHA256 hash of a file.', {'path': 'string'}),
    ('count_lines', 'Count lines in a file.', {'path': 'string'}),
    ('validate_json', 'Validate JSON file syntax.', {'path': 'string'}),
    ('check_encoding', 'Check text file encoding.', {'path': 'string'}),
    ('run_sql', 'Execute SQL query against database.', {'sql': 'string'}),
    ('send_slack', 'Send message to Slack channel.', {'channel': 'string', 'text': 'string'}),
    ('create_ticket', 'Create a JIRA ticket.', {'title': 'string', 'body': 'string'}),
    ('profile_code', 'Profile Python code execution.', {'path': 'string'}),
    ('benchmark_run', 'Run a benchmark suite.', {'name': 'string'}),
    ('export_csv', 'Export data to CSV file.', {'query': 'string', 'out': 'string'}),
    ('import_csv', 'Import CSV to database.', {'path': 'string', 'table': 'string'}),
    ('list_processes', 'List running processes.', {}),
    ('kill_process', 'Kill a process by PID.', {'pid': 'integer'}),
    ('check_port', 'Check if a port is in use.', {'port': 'integer'}),
    ('ping_host', 'Ping a network host.', {'host': 'string'}),
    ('dns_lookup', 'Perform DNS lookup.', {'domain': 'string'}),
    ('parse_yaml', 'Parse YAML file.', {'path': 'string'}),
    ('merge_yaml', 'Merge two YAML files.', {'path1': 'string', 'path2': 'string'}),
    ('diff_files', 'Compute diff between two files.', {'a': 'string', 'b': 'string'}),
    ('patch_file', 'Apply a patch file.', {'patch': 'string', 'target': 'string'}),
    ('find_deps', 'Find package dependencies.', {'package': 'string'}),
    ('tree_dir', 'Print directory tree structure.', {'path': 'string'}),
    ('pip_outdated', 'List outdated pip packages.', {}),
    ('npm_outdated', 'List outdated npm packages.', {}),
    ('docker_ps', 'List running docker containers.', {}),
    ('docker_logs', 'Fetch docker container logs.', {'container': 'string'}),
    ('k8s_pods', 'List Kubernetes pods.', {'namespace': 'string'}),
    ('aws_s3_ls', 'List AWS S3 bucket contents.', {'bucket': 'string'}),
    ('gcp_bq_query', 'Run BigQuery SQL.', {'sql': 'string'}),
    ('prom_query', 'Query Prometheus metrics.', {'query': 'string'}),
    ('grafana_get', 'Fetch Grafana panel data.', {'panel_id': 'integer'}),
    ('measure_latency', 'Measure HTTP endpoint latency.', {'url': 'string'}),
    ('http_post', 'Send HTTP POST request.', {'url': 'string', 'body': 'string'}),
    ('http_get', 'Send HTTP GET request.', {'url': 'string'}),
    ('compress_file', 'Compress file with gzip.', {'path': 'string'}),
    ('decompress_file', 'Decompress gzip file.', {'path': 'string'}),
]


class NoopTool(BaseTool):
    """Noop 工具：返回"不支持"，不执行任何真实操作。"""

    def __init__(self, name: str, description: str, params: dict):
        self._name = name
        self._description = description
        self._params = params
        self.name = name
        self.read_only = True

    def get_schema(self) -> dict:
        properties = {}
        for pname, ptype in self._params.items():
            properties[pname] = {'type': ptype, 'description': f'{pname} parameter'}
        return {
            'name': self._name,
            'description': self._description,
            'parameters': {
                'type': 'object',
                'properties': properties,
                'required': list(self._params.keys()),
            },
        }

    def execute(self, args, config):
        # 理论上不会被调到（Agent 应该知道 noop 工具没用）
        return True, f'(noop) {self._name} invoked with {args}'


# ============================================================
# Capture-only 包装（复用 exp1 的思路）
# ============================================================

class CaptureOnlyTool(BaseTool):
    """只捕获决策，不真正执行破坏性操作。"""

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
        if isinstance(self.real, NoopTool):
            return self.real.execute(args, config)
        if self.real.read_only:
            try:
                return self.real.execute(args, config)
            except Exception as e:
                return False, f'(simulated exec error) {e}'
        # 破坏性工具：返回假成功
        if self.name == 'write_file':
            return True, f'(simulated) Created {args.get("path","?")}.'
        if self.name == 'edit_file':
            return True, f'(simulated) Applied edit to {args.get("path","?")}.'
        if self.name == 'bash':
            return True, f'(simulated) Command executed successfully.'
        return True, '(simulated) ok'


def build_registry(tool_count: int, captured: list) -> ToolRegistry:
    """构造指定规模的工具集：6 真实 + (tool_count-6) noop。"""
    real_registry = create_default_registry()
    apply_descriptions(real_registry, 'v2')

    wrapped = ToolRegistry()
    # 真实工具（按 tool_count 限制）
    real_tools = list(real_registry.list_tools())
    # 3档：只保留 read_file/edit_file/bash 这三个常用
    if tool_count == 3:
        wanted = {'read_file', 'edit_file', 'bash'}
        real_tools = [t for t in real_tools if t.name in wanted]
    # 6档及以上：完整6个
    for tool in real_tools:
        wrapped.register(CaptureOnlyTool(tool, captured))

    # 补 noop
    needed = tool_count - len(real_tools)
    for i in range(needed):
        spec = NOOP_TEMPLATES[i % len(NOOP_TEMPLATES)]
        # 保证 name 唯一：超过 42 时加后缀
        name = spec[0] if i < len(NOOP_TEMPLATES) else f'{spec[0]}_{i}'
        noop = NoopTool(name, spec[1], spec[2])
        wrapped.register(CaptureOnlyTool(noop, captured))

    return wrapped


# ============================================================
# 单任务跑一次
# ============================================================

def run_single(case: dict, tool_count: int, seed: int) -> dict:
    captured: list = []
    registry = build_registry(tool_count, captured)

    status = 'ok'
    error = ''
    input_tokens = output_tokens = 0
    t_start = time.time()
    try:
        result = run(
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
        if result:
            input_tokens = getattr(result, 'input_tokens', 0) or 0
            output_tokens = getattr(result, 'output_tokens', 0) or 0
    except Exception as exc:
        status = 'error'
        error = f'{type(exc).__name__}: {exc}'

    duration = time.time() - t_start

    # 打分
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
        'tool_count': tool_count,
        'seed': seed,
        'first_call': first,
        'all_calls': captured,
        'n_calls': len(captured),
        'first_call_right': first_call_right,
        'any_call_right': any_call_right,
        'forbidden_hit': forbidden_hit,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': input_tokens + output_tokens,
        'duration_sec': round(duration, 2),
        'status': status,
        'error': error,
    }


def load_existing_results(out_path: Path) -> tuple[list, set]:
    """支持中断续跑：读已有结果，跳过已完成的 (id, tool_count, seed)。"""
    if not out_path.exists():
        return [], set()
    try:
        existing = json.loads(out_path.read_text(encoding='utf-8'))
        results = existing.get('results', [])
        done_keys = {(r['id'], r['tool_count'], r['seed']) for r in results}
        return results, done_keys
    except Exception:
        return [], set()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true', help='1档 × 5任务 × 1种子')
    parser.add_argument('--tool-count', type=int, default=None,
                        help='只跑指定档位，如 12')
    parser.add_argument('--seeds', type=int, default=3, help='使用前 N 个种子')
    parser.add_argument('--limit', type=int, default=None, help='只跑前 N 个任务')
    parser.add_argument('--sleep', type=float, default=0.3)
    parser.add_argument('--out', default='results.json')
    args = parser.parse_args()

    if not os.environ.get('DEEPSEEK_API_KEY'):
        print('[错误] 未设置 API key。请在 .env 中配置以下任意一个：')
        print('  DEEPSEEK_API_KEY / HARNESS_API_KEY / OPENAI_API_KEY')
        sys.exit(1)

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / args.out

    # 加载任务
    cases = [json.loads(l) for l in GOLDEN_SET.read_text(encoding='utf-8').splitlines() if l.strip()]

    # 配置档位
    if args.smoke:
        # 业界 eval smoke 设计三条：跨档位预览趋势 / 覆盖所有任务类别 / 验证
        # 关键边界（noop 干扰是否生效、48 档是否撞 API 限制）。
        # 选 6（基线）和 48（极端）两档，每档每类抽 1-2 条，1 seed，约 20-30 次调用。
        tool_counts = [6, 48]
        by_cat: dict = {}
        for c in cases:
            by_cat.setdefault(c.get('category', 'unknown'), []).append(c)
        # 每类抽 1 条；bash_positive 因为需要验证 48 档下的合法用法不被挤走，多抽 1 条
        sampled: list = []
        for cat, cs in by_cat.items():
            take = 2 if cat == 'bash_positive' else 1
            sampled.extend(cs[:take])
        cases = sampled
        seeds = [42]
    elif args.tool_count is not None:
        tool_counts = [args.tool_count]
        seeds = list(range(42, 42 + args.seeds))
    else:
        tool_counts = TOOL_COUNTS
        seeds = list(range(42, 42 + args.seeds))

    if args.limit:
        cases = cases[:args.limit]

    # 读已有结果支持续跑
    results, done_keys = load_existing_results(out_path)
    total = len(tool_counts) * len(cases) * len(seeds)
    done = len(done_keys)

    print(f'=== Exp2 Tool Count Impact ===')
    print(f'  Tool counts: {tool_counts}')
    print(f'  Cases: {len(cases)}, Seeds: {seeds}')
    print(f'  Total: {total}, Already done: {done}')
    print()

    start = time.time()
    for tc in tool_counts:
        for case in cases:
            for seed in seeds:
                key = (case['id'], tc, seed)
                if key in done_keys:
                    continue
                obs = run_single(case, tc, seed)
                results.append(obs)
                done += 1
                mark = '  FC' if obs['first_call_right'] else ('  AC' if obs['any_call_right'] else 'FAIL')
                got = obs['first_call']['name'] if obs['first_call'] else '<no>'
                elapsed = time.time() - start
                print(f'[tc={tc}] [{done:4d}/{total}] {case["id"]:6s} s={seed} '
                      f'want={case.get("expected_tool") or "<no>":13s} got={got:13s} {mark}  '
                      f'({elapsed:.0f}s elapsed)')
                # 增量写盘，防崩溃
                _save(out_path, tool_counts, seeds, len(cases), results)
                time.sleep(args.sleep)

    _summarize(results, tool_counts, out_path)
    return 0


def _save(path: Path, tool_counts, seeds, num_cases, results):
    summary = {
        'tool_counts': tool_counts,
        'seeds': seeds,
        'num_cases': num_cases,
        'num_observations': len(results),
    }
    path.write_text(
        json.dumps({'summary': summary, 'results': results}, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def _summarize(results, tool_counts, out_path):
    print()
    print(f'=== 汇总 (n={len(results)}) ===')
    print(f'{"tool_count":12s} {"n":4s} {"FC%":6s} {"AC%":6s} {"AvgCalls":9s} {"AvgToks":9s}')
    for tc in tool_counts:
        rs = [r for r in results if r['tool_count'] == tc]
        if not rs:
            continue
        n = len(rs)
        fc = sum(1 for r in rs if r['first_call_right']) / n
        ac = sum(1 for r in rs if r['any_call_right']) / n
        ac_calls = sum(r['n_calls'] for r in rs) / n
        avg_tok = sum(r['total_tokens'] for r in rs) / n
        print(f'{tc:<12} {n:<4} {fc*100:5.1f}% {ac*100:5.1f}% {ac_calls:<9.2f} {avg_tok:<9.0f}')
    print(f'\n结果: {out_path}')


if __name__ == '__main__':
    sys.exit(main())
