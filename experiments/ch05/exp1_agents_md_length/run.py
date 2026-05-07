"""
实验一：AGENTS.md 长度效应
============================
在 harness-py + DeepSeek 上测量 AGENTS.md (CLAUDE.md) 不同长度对
Agent 修复 bug 任务的影响。

配置：
  - 3 个任务（cost_tracker_bug / retry_decorator_bug / csv_parser_bug）
  - 4 档文档（L0 无 / L1 精简 / L2 标准 / L3 冗长）
  - 5 个种子（通过变化 temperature 和 seed 实现）

默认跑 3 × 4 × 5 = 60 次任务。每次约 8-15 轮。

用法:
    # 最小冒烟：1任务 × 1档 × 1种子 = 1次
    python run.py --smoke

    # 单任务单档位（用于调试 fixture）
    python run.py --task cost_tracker_bug --variant L0 --seeds 1

    # 全量
    python run.py

    # 仅重绘：加载已有结果不重跑
    python run.py --replot-only
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
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

# === 隔离 CLAUDE.md 发现 ===
# 仅读 cwd 根下的 CLAUDE.md，不向上遍历。
# 避免 harness-py-book 仓库自身的 CLAUDE.md 污染实验。
import harness_py.prompt as _prompt_mod  # noqa: E402


def _isolated_discover(cwd):
    cwd = Path(cwd) if not isinstance(cwd, Path) else cwd
    claude = cwd.resolve() / 'CLAUDE.md'
    if claude.exists():
        try:
            return [(Path('CLAUDE.md'), claude.read_text(encoding='utf-8'))]
        except Exception:
            return []
    return []


_prompt_mod.discover_claude_md = _isolated_discover

from harness_py.agent import run  # noqa: E402
from harness_py.config import AgentConfig, ModelConfig  # noqa: E402

# === 实验配置 ===
EXP_DIR = Path(__file__).parent
FIXTURES_DIR = EXP_DIR / 'fixtures'
VARIANTS_DIR = EXP_DIR / 'agents_md_variants'
RESULTS_DIR = EXP_DIR / 'results'
WORKDIR_ROOT = EXP_DIR / '_workdir'

TASKS = ['cost_tracker_bug', 'retry_decorator_bug', 'csv_parser_bug']
VARIANTS = ['L0', 'L1', 'L2', 'L3']
SEEDS = [42, 7, 123, 2024, 99]


def prepare_workdir(task_name: str, variant: str, run_tag: str) -> Path:
    """在隔离目录中准备 fixture + 对应档位的 CLAUDE.md。"""
    src = FIXTURES_DIR / task_name
    tmp = WORKDIR_ROOT / f'{task_name}__{variant}__{run_tag}'
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    # 复制源码和测试，不包含 task_description 和 pytest 缓存
    for f in src.iterdir():
        if f.name == 'task_description.txt':
            continue
        if f.is_dir():  # 跳过 __pycache__, .pytest_cache 等
            continue
        if f.name.startswith('.'):
            continue
        shutil.copy(f, tmp / f.name)

    # 按档位安装 CLAUDE.md
    if variant == 'L0':
        pass  # 不装
    else:
        variant_file = VARIANTS_DIR / {
            'L1': 'L1_concise.md',
            'L2': 'L2_standard.md',
            'L3': 'L3_verbose.md',
        }[variant]
        shutil.copy(variant_file, tmp / 'CLAUDE.md')

    return tmp


def verify_with_pytest(workdir: Path) -> tuple[bool, str]:
    """跑 pytest，返回 (是否全部通过, 摘要)。"""
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'test_expected.py', '-q', '--no-header'],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return False, 'pytest timeout'
    except Exception as exc:
        return False, f'pytest error: {exc}'

    tail = (proc.stdout + proc.stderr).strip().splitlines()[-5:]
    return proc.returncode == 0, '\n'.join(tail)


def run_single(
    task_name: str, variant: str, seed: int, repeat_idx: int, temperature: float
) -> dict:
    """跑一次，返回度量指标。"""
    run_tag = f'seed{seed}_r{repeat_idx}'
    workdir = prepare_workdir(task_name, variant, run_tag)
    task_desc = (FIXTURES_DIR / task_name / 'task_description.txt').read_text(
        encoding='utf-8'
    )

    mc = ModelConfig.from_env()
    # DeepSeek 目前 seed 支持通过 http 请求体传递；
    # 这里通过修改环境变量的方式交给 http_client 透传。
    # 若 http_client 不支持 seed，temperature 的微调仍能产生轻量差异。
    mc.temperature = temperature

    ac = AgentConfig(
        cwd=workdir,
        max_iterations=25,
        planning_turns=2,
        allow_shell=True,  # 需要跑 pytest
        allow_destructive=False,
    )

    result = None
    api_error = None
    t_start = time.time()
    try:
        result = run(task_desc, model_config=mc, agent_config=ac)
    except Exception as exc:
        api_error = f'{type(exc).__name__}: {exc}'
    duration = time.time() - t_start

    # 独立验证（不依赖 Agent 的自我报告）
    passed, verify_tail = verify_with_pytest(workdir)

    metrics = {
        'task': task_name,
        'variant': variant,
        'seed': seed,
        'repeat': repeat_idx,
        'temperature': temperature,
        'success': passed,
        'verify_tail': verify_tail,
        'turns': result.turns if result else 0,
        'tool_calls': result.tool_calls if result else 0,
        'total_tokens': result.total_tokens if result else 0,
        'stop_reason': result.stop_reason if result else 'exception',
        'duration_sec': round(duration, 2),
        'api_error': api_error,
    }
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true', help='1×1×1 最小规模')
    parser.add_argument('--task', default='all', help='all 或具体 task 名')
    parser.add_argument('--variant', default='all', help='all 或 L0/L1/L2/L3')
    parser.add_argument('--seeds', type=int, default=5, help='使用前 N 个种子')
    parser.add_argument('--repeats', type=int, default=1, help='每组重复次数')
    parser.add_argument('--out', default='results.json')
    parser.add_argument('--sleep', type=float, default=2.0, help='每次之间的间隔秒数')
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    WORKDIR_ROOT.mkdir(exist_ok=True)

    if args.smoke:
        tasks = ['cost_tracker_bug']
        variants = ['L0']
        seeds = [42]
        repeats = 1
    else:
        tasks = TASKS if args.task == 'all' else [args.task]
        variants = VARIANTS if args.variant == 'all' else [args.variant]
        seeds = SEEDS[: args.seeds]
        repeats = args.repeats

    # 温度：不同 seed 用略微不同的 temperature 引入变化
    # temperature=0.0 给 DeepSeek 接近确定性输出，但不是严格确定
    # 使用 0.2 作为基线 + seed 相关的微小扰动
    temp_by_seed = {s: round(0.2 + (idx * 0.05), 2) for idx, s in enumerate(seeds)}

    all_results: list[dict] = []
    out_path = RESULTS_DIR / args.out

    total = len(tasks) * len(variants) * len(seeds) * repeats
    done = 0
    t_batch_start = time.time()

    for task in tasks:
        for variant in variants:
            for seed in seeds:
                for r_idx in range(repeats):
                    done += 1
                    temp = temp_by_seed[seed]
                    label = f'{task} / {variant} / seed={seed}(T={temp}) / r{r_idx}'
                    elapsed = time.time() - t_batch_start
                    print(
                        f'\n[{done}/{total}] elapsed={elapsed:.0f}s  {label}',
                        flush=True,
                    )
                    metrics = run_single(task, variant, seed, r_idx, temp)
                    all_results.append(metrics)
                    # 增量写盘，防止中途崩溃丢数据
                    out_path.write_text(
                        json.dumps(all_results, ensure_ascii=False, indent=2),
                        encoding='utf-8',
                    )
                    print(
                        f'  -> success={metrics["success"]} '
                        f'turns={metrics["turns"]} '
                        f'tokens={metrics["total_tokens"]} '
                        f'stop={metrics["stop_reason"]!r}',
                        flush=True,
                    )
                    if args.sleep > 0:
                        time.sleep(args.sleep)

    print(f'\n完成 {done} 次任务，结果写入 {out_path}')
    print(f'总耗时: {time.time() - t_batch_start:.0f} 秒')
    return 0


if __name__ == '__main__':
    sys.exit(main())
