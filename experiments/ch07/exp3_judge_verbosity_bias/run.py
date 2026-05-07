"""
闭环验证策略对照实验
======================
对应书稿 7.2 节。同一组 bug fix 任务在 5 种闭环验证策略下跑，量化业界关心
的真实问题：闭环验证的不同设计如何影响通过率、成本、假阳性率。

5 种策略全都是闭环（都能跑测试），差异在策略层面：
  s1_baseline           跑全量 pytest + 完整 traceback + 自评
  s2_test_selection     只跑受影响模块的测试 + 完整 traceback + 自评
  s3_lint_first         先 py_compile 检查语法，过了再跑测试
  s4_independent_judge  全量 + 独立 judge Agent 评审（无共享上下文）
  s5_compressed_feedback 全量 + 失败信息 LLM 压缩到 ~150 字符

样本：
  --smoke:  3 任务 × 5 策略 × 1 seed = 15
  full:     10 任务 × 5 策略 × 3 seeds = 150

用法：
    python run.py --smoke
    python run.py
    python run.py --strategy s4_independent_judge   # 只跑某一档
    python run.py --tasks-set hard                  # 只跑 5 个难任务
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
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

# API key 兼容：DEEPSEEK / HARNESS / OPENAI 任一即可
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

from harness_py_pro.config import AgentConfig, ModelConfig
from harness_py_pro.engine import run as engine_run
from harness_py_pro.tools import create_default_registry

from strategies import ALL_STRATEGIES, get_strategy

EXP_DIR = Path(__file__).parent
TASKS_FILE = EXP_DIR / 'tasks' / 'bugs.jsonl'
FIXTURES = EXP_DIR / 'fixtures'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)
WORKDIR = EXP_DIR / 'workdir'
WORKDIR.mkdir(exist_ok=True)

# 自报关键词
_SELF_REPORT_PATTERNS = re.compile(
    r'(已修复|修复完成|已完成|fixed|done|completed|all\s+tests\s+pass)',
    re.IGNORECASE,
)

# 难任务集合（5 个）
HARD_TASK_IDS = {'bm001', 'al003', 'im001', 'rt001', 'ds001'}
# 对抗任务集合（5 个）—— 专为差异化策略选型设计
ADVERSARIAL_TASK_IDS = {'adv001', 'adv002', 'adv003', 'adv004', 'adv005'}
# 盲区任务集合 —— 多文件 fixture，专打某一档策略的盲点
BLINDSPOT_TASK_IDS = {'xm001', 'dp001'}


@dataclass
class Result:
    task_id: str
    category: str
    strategy: str
    seed: int
    final_pytest_pass: int       # 1 = 干净 pytest 全通过（ground truth）
    self_report_success: int     # 1 = Agent 报告完成
    judge_verdict: str           # DONE / NOT_DONE / 空（仅 S4 有）
    agent_turns: int
    pytest_calls: int
    cost_usd: float
    wall_seconds: float
    error: str = ''


def setup_workspace(task: dict, run_id: str) -> Path:
    """复制 fixture 到独立 workdir。

    支持两种 fixture 布局：
    1. **单文件**（默认）：fixtures/<module>.py + fixtures/test_<module>.py
       适合简单 bug fix。
    2. **多文件**（task['multi_file']==True）：fixtures/<task_id>/ 整个目录
       结构通常是 src/*.py + tests/test_*.py，适合跨模块 bug。
    """
    work = WORKDIR / run_id
    if work.exists():
        # Windows 上 __pycache__ 偶尔被另一个 python 进程锁住，rmtree 会失败。
        # 重试几次 + 最后退路用唯一后缀，绝不让一次清理失败拖垮整轮 smoke。
        for attempt in range(3):
            try:
                shutil.rmtree(work)
                break
            except OSError:
                time.sleep(2)
        else:
            work = WORKDIR / f'{run_id}_{int(time.time())}'

    # 多文件 fixture
    if task.get('multi_file'):
        multi_dir = FIXTURES / task['id']
        if not multi_dir.is_dir():
            raise FileNotFoundError(f'multi_file fixture dir not found: {multi_dir}')
        shutil.copytree(multi_dir, work)
        # conftest 让 src/ 和 tests/ 都能 import 到对方
        (work / 'conftest.py').write_text(
            'import sys, pathlib\n'
            'sys.path.insert(0, str(pathlib.Path(__file__).parent))\n',
            encoding='utf-8',
        )
        return work

    # 单文件 fixture（原有逻辑）
    work.mkdir(parents=True)
    src_path = EXP_DIR / task['module']
    if not src_path.exists():
        raise FileNotFoundError(f'fixture not found: {src_path}')
    target_name = Path(task['module']).name
    shutil.copy2(src_path, work / target_name)

    test_name = 'test_' + target_name
    test_src = FIXTURES / test_name
    if not test_src.exists():
        raise FileNotFoundError(f'test fixture not found: {test_src}')
    (work / 'tests').mkdir(exist_ok=True)
    shutil.copy2(test_src, work / 'tests' / test_name)
    (work / 'conftest.py').write_text(
        'import sys, pathlib\n'
        'sys.path.insert(0, str(pathlib.Path(__file__).parent))\n',
        encoding='utf-8',
    )
    return work


def run_pytest(workdir: Path) -> tuple[int, str]:
    """干净跑一次 pytest（ground truth），返回 (exit_code, output)。"""
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-q', '--tb=short'],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return -1, 'TIMEOUT'
    except Exception as e:
        return -2, f'{type(e).__name__}: {e}'


def count_pytest_calls(workdir: Path, session_id: str) -> int:
    """从 session.jsonl 数 Agent 跑 bash("pytest ...") 的次数。

    pytest 失败时 ok=False，S5 压缩 wrapper 也会改变 result_preview 格式，
    所以只要命令含 pytest 且实际执行（result_preview 非空）就算一次。
    shell 级失败的特征是 preview 里有 'No such file' / 'command not found'。
    """
    session_path = workdir / '.harness_sessions' / f'{session_id}.jsonl'
    if not session_path.exists():
        return 0
    count = 0
    try:
        for line in session_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') != 'tool_call' or event.get('tool') != 'bash':
                continue
            cmd = (event.get('args') or {}).get('command', '')
            if 'pytest' not in cmd:
                continue
            preview = event.get('result_preview') or ''
            if any(m in preview for m in ('No such file', 'command not found', 'cd:')):
                continue
            count += 1
    except OSError:
        return 0
    return count


def run_one(task: dict, strategy_name: str, seed: int) -> Result:
    """跑一次 (task, strategy, seed)。

    流程：
      1. 复制 fixture 到隔离 workdir
      2. 实例化策略，按策略追加 prompt + wrap tools
      3. engine.run() 执行
      4. 独立 pytest 验证 final_pytest_pass（不信 Agent 自报）
      5. 数 pytest_calls 看 Agent 真实使用反馈的频率
      6. S4 策略额外跑独立 judge
    """
    run_id = f"{task['id']}_{strategy_name}_{seed}"
    workdir = setup_workspace(task, run_id)
    strategy = get_strategy(strategy_name)

    # bash 用 git-bash，cd 时用相对路径或忽略 cd——cwd 已经设到 workdir
    bash_hint = (
        '\n(bash 工具的 cwd 已经是项目根目录，不需要 cd；直接 `pytest tests/ -q` 即可。)'
    )
    # 构造 prompt
    if task.get('multi_file'):
        # 多文件 fixture：source 路径在 user_prompt 里说清楚，这里只给项目结构
        base_prompt = (
            f"项目根目录是 {workdir}。\n"
            f"项目结构：./src/ 是源码，./tests/ 是测试。运行 `pytest tests/ -q` 跑全量测试。"
            f"{bash_hint}\n\n"
            f"任务：{task['user_prompt']}"
        )
    else:
        base_prompt = (
            f"项目根目录是 {workdir}。需要修复的源文件是 ./{Path(task['module']).name}。\n"
            f"测试在 ./tests/test_{Path(task['module']).name} 中，要求修复后能让所有测试通过。"
            f"{bash_hint}\n\n"
            f"任务：{task['user_prompt']}"
        )
    user_prompt = base_prompt + strategy.get_prompt_addendum()

    # 配 Agent
    ac = AgentConfig(
        cwd=workdir,
        max_iterations=8,           # 5 策略统一上限，避免某档跑飞
        planning_turns=0,
        allow_write=True,
        allow_shell=True,           # 5 档全是闭环，都需要 bash
        sandbox_mode='bypass',
        network_isolated=True,
    )
    mc = ModelConfig(
        model='deepseek-chat',
        api_key=os.environ['DEEPSEEK_API_KEY'],
        base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1'),
        context_window=64000,
        temperature=0.0,
        seed=seed,
    )

    # 构造 ToolRegistry（让策略包装 bash 等）
    registry = strategy.wrap_tools(create_default_registry())

    t0 = time.time()
    err = ''
    self_report = 0
    turns = 0
    pytest_calls = 0
    cost = 0.0
    output = ''
    judge_verdict = ''
    session_id = ''

    try:
        result = engine_run(
            task=user_prompt,
            model_config=mc,
            agent_config=ac,
            tool_registry=registry,
            verbose=False,
        )
        turns = result.turns
        cost = result.cost_usd
        output = result.output or ''
        session_id = result.session_id
        if output and _SELF_REPORT_PATTERNS.search(output):
            self_report = 1
        pytest_calls = count_pytest_calls(workdir, session_id)
    except Exception as e:
        err = f'{type(e).__name__}: {e}'

    # ground truth：独立子进程跑 pytest
    code, _ = run_pytest(workdir)
    final_pass = int(code == 0)

    # 任何带 judge 的策略：跑独立 judge
    if strategy_name in (
        's4_independent_judge', 's7_spec_aware_judge',
        's8_bp_judge', 's9_spec_aware_bp_judge',
    ) and not err:
        try:
            judge_result = strategy.post_run_judge(workdir, output)
            judge_verdict = judge_result.get('judge_verdict') or ''
        except Exception as e:
            judge_verdict = f'(judge error: {type(e).__name__})'

    return Result(
        task_id=task['id'],
        category=task['category'],
        strategy=strategy_name,
        seed=seed,
        final_pytest_pass=final_pass,
        self_report_success=self_report,
        judge_verdict=judge_verdict,
        agent_turns=turns,
        pytest_calls=pytest_calls,
        cost_usd=round(cost, 4),
        wall_seconds=round(time.time() - t0, 2),
        error=err,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--strategy', choices=list(ALL_STRATEGIES) + ['all'], default='all',
                    help='只跑某一档策略（默认全部 5 档）')
    ap.add_argument('--tasks-set',
                    choices=['simple', 'hard', 'adversarial', 'blindspot', 'all'],
                    default='simple',
                    help='simple=简单任务，hard=5 难任务，adversarial=5 对抗任务，'
                         'blindspot=多文件盲区任务，all=全部')
    ap.add_argument('--seeds', type=int, nargs='+', default=[42, 7, 123])
    args = ap.parse_args()

    # 选任务
    with TASKS_FILE.open(encoding='utf-8') as fh:
        all_tasks = [json.loads(line) for line in fh if line.strip()]
    if args.tasks_set == 'simple':
        tasks = [t for t in all_tasks
                 if t['id'] not in HARD_TASK_IDS
                 and t['id'] not in ADVERSARIAL_TASK_IDS
                 and t['id'] not in BLINDSPOT_TASK_IDS]
    elif args.tasks_set == 'hard':
        tasks = [t for t in all_tasks if t['id'] in HARD_TASK_IDS]
    elif args.tasks_set == 'adversarial':
        tasks = [t for t in all_tasks if t['id'] in ADVERSARIAL_TASK_IDS]
    elif args.tasks_set == 'blindspot':
        tasks = [t for t in all_tasks if t['id'] in BLINDSPOT_TASK_IDS]
    else:
        tasks = all_tasks

    if args.smoke:
        tasks = tasks[:3]
        seeds = [args.seeds[0]]
    else:
        seeds = args.seeds

    strategies = list(ALL_STRATEGIES) if args.strategy == 'all' else [args.strategy]
    total = len(tasks) * len(strategies) * len(seeds)
    print(f"=== Ch7 exp1 闭环策略对照 ===")
    print(f"  tasks={len(tasks)} strategies={strategies} seeds={seeds}  共 {total} 次")

    out_path = RESULTS / 'raw.jsonl'
    n = 0
    with out_path.open('w', encoding='utf-8') as fh:
        for task in tasks:
            for strategy in strategies:
                for seed in seeds:
                    n += 1
                    r = run_one(task, strategy, seed)
                    fh.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')
                    fh.flush()
                    flag = '✓' if r.final_pytest_pass else '✗'
                    err = f' ERR={r.error[:40]}' if r.error else ''
                    judge = f' judge={r.judge_verdict}' if r.judge_verdict else ''
                    print(
                        f"  [{n:>3}/{total}] {r.task_id} {r.strategy:24} seed={seed} {flag} "
                        f"self_report={r.self_report_success} pytest={r.pytest_calls} "
                        f"turns={r.agent_turns} cost=${r.cost_usd:.3f}{judge}{err}"
                    )

    print(f"\n完成 → {out_path}")
    print(f"\n旧 open vs closed 数据保留在 results/raw_openclosed_baseline.jsonl")


if __name__ == '__main__':
    main()
