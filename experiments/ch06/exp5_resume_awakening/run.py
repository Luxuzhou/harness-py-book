"""
实验五：三步唤醒对恢复后质量的影响
=======================================
对应书稿 6.5.3。

流程：
  阶段 A：启动 Agent 跑 10 步重构任务，max_iterations 限定让它只能做完前 5 步
  阶段 B：用两种不同的 prompt 恢复，观察恢复后前 5 轮的行为

自变量：resume_prompt ∈ {plain, three_step_wakeup}
因变量：wrong_dir_errors、stale_assumptions、repeated_steps、
        time_to_first_productive_turn、final_pytest_pass

用法：
    python run.py --smoke
    python run.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _force_rmtree(path: Path) -> None:
    """Windows 友好的 rmtree：.git/objects 下的文件常被标记只读，
    默认 shutil.rmtree 会 PermissionError；此处在 onexc 里清只读再重试。"""
    def _handler(func, p, exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    # Python 3.12+ 用 onexc 替代 onerror
    shutil.rmtree(path, onexc=_handler)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_env_file = _REPO_ROOT / '.env'
if _env_file.exists():
    for _line in _env_file.read_text(encoding='utf-8').splitlines():
        if '=' in _line and not _line.strip().startswith('#'):
            k, _, v = _line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())
sys.path.insert(0, str(_REPO_ROOT))

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

from harness_py.agent import run, resume  # noqa: E402
from harness_py.config import AgentConfig, ModelConfig  # noqa: E402
from harness_py.session import load_session_messages  # noqa: E402

EXP_DIR = Path(__file__).parent
FIXTURES = EXP_DIR / 'fixtures'
WORKDIR = EXP_DIR / '_workdir'
RESULTS = EXP_DIR / 'results'
RESULTS.mkdir(exist_ok=True)

PLAIN_PROMPT = '请继续之前未完成的工作。'
THREE_STEP_PROMPT = (
    '在继续任务前，请先完成三步状态确认：\n'
    '1. 运行 `bash pwd` 输出当前工作目录\n'
    '2. 运行 `bash git log --oneline -10` 查看最近变更（若非 git 仓库则跳过）\n'
    '3. 读取 TASK.md 文件获取任务进度\n'
    '然后根据 TASK.md 的进度继续执行剩余步骤，不要重复已完成的步骤。'
)


@dataclass
class TrialResult:
    variant: str           # 'plain' | 'three_step'
    seed: int
    phase_a_turns: int
    phase_b_turns: int
    wrong_dir_errors: int
    repeated_step_attempts: int
    stale_file_assumptions: int
    first_productive_turn: int  # 1-index，-1 表示整个恢复阶段没有推进
    # 明确基线：区分 Phase A 完成 vs Phase B 增量完成
    phase_a_done_count: int     # Phase A 结束时的完成步骤数
    phase_b_done_count: int     # Phase B 结束时的完成步骤数（最终）
    incremental_steps: int      # = phase_b_done_count - phase_a_done_count
    final_completed_steps: int  # 等价于 phase_b_done_count（保留兼容字段）
    wall_seconds: float


# ============ 启发式指标 ============
# 判定 "错误目录 / 重复步骤 / 过时假设" 的规则
WRONG_DIR_MARKERS = [
    r'(?i)no such file or directory',
    r'(?i)cannot find',
    r"(?i)file not found",
]

# 完成步骤 N 会在 TASK.md 或 session 中留下 "- [x] 步骤 N" 标记
STEP_DONE_RE = re.compile(r'-\s+\[x\]\s+步骤\s+(\d+)')


def count_wrong_dir_errors(messages: list[dict]) -> int:
    count = 0
    for m in messages:
        if m.get('role') != 'tool':
            continue
        content = str(m.get('content', ''))
        for pat in WRONG_DIR_MARKERS:
            if re.search(pat, content):
                count += 1
                break
    return count


def count_repeated_steps(messages: list[dict], phase_a_done: set[int]) -> int:
    """统计恢复阶段 Agent 试图重做已完成步骤的次数。"""
    count = 0
    for m in messages:
        if m.get('role') != 'assistant':
            continue
        content = str(m.get('content', ''))
        for match in re.finditer(r'步骤\s*(\d+)', content):
            step_n = int(match.group(1))
            if step_n in phase_a_done:
                count += 1
                break
    return count


def find_first_productive_turn(messages: list[dict], phase_a_done: set[int]) -> int:
    """恢复阶段第一条明确推进到新步骤 N 的 assistant 消息轮次（1-index）。"""
    turn = 0
    for m in messages:
        if m.get('role') != 'assistant':
            continue
        turn += 1
        content = str(m.get('content', ''))
        for match in re.finditer(r'步骤\s*(\d+)', content):
            step_n = int(match.group(1))
            if step_n not in phase_a_done:
                return turn
    return -1


def count_completed_steps(workdir: Path) -> int:
    """从 TASK.md 读取完成的步骤数。如果不存在就用 pytest 测试文件存在性近似。"""
    task_md = workdir / 'TASK.md'
    if task_md.exists():
        text = task_md.read_text(encoding='utf-8', errors='ignore')
        done = set(int(m.group(1)) for m in STEP_DONE_RE.finditer(text))
        return len(done)
    # fallback: 检查 string_utils.py、date_utils.py 等产物
    expected_files = [
        'string_utils.py', 'date_utils.py', 'constants.py',
    ]
    return sum(1 for f in expected_files if (workdir / f).exists())


# ============ 初始代码库 ============
INITIAL_UTILS_PY = '''"""Utils 起始版本。"""
import time

MAX_SLUG_LEN = 50
DEFAULT_TZ = 'UTC'


def slugify(s):
    """把字符串转 slug。"""
    return s.lower().replace(' ', '-')[:MAX_SLUG_LEN]


def camel_to_snake(s):
    import re
    return re.sub(r'([A-Z])', r'_\\1', s).lower().strip('_')


def truncate(s, n):
    return s if len(s) <= n else s[:n-3] + '...'


def parse_iso(s):
    from datetime import datetime
    return datetime.fromisoformat(s)


def to_unix(dt):
    return int(dt.timestamp())


def format_duration(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f'{h}h{m}m{s}s'
'''

INITIAL_TASK_MD = '''# TASK.md

- [ ] 步骤 1：拆分字符串工具
- [ ] 步骤 2：拆分日期工具
- [ ] 步骤 3：为 string_utils.py 添加类型标注
- [ ] 步骤 4：为 date_utils.py 添加类型标注
- [ ] 步骤 5：提取公共常量到 constants.py
- [ ] 步骤 6：添加 docstring
- [ ] 步骤 7：重构 truncate
- [ ] 步骤 8：添加 slugify 的多语言支持
- [ ] 步骤 9：提取测试共用 fixture
- [ ] 步骤 10：更新 README.md
'''

INITIAL_README = '# Utils 工具库\n\n待重构。\n'


def prepare_workdir(variant: str, seed: int) -> Path:
    wd = WORKDIR / f'{variant}_seed{seed}'
    if wd.exists():
        _force_rmtree(wd)
    wd.mkdir(parents=True)
    (wd / 'utils.py').write_text(INITIAL_UTILS_PY, encoding='utf-8')
    (wd / 'TASK.md').write_text(INITIAL_TASK_MD, encoding='utf-8')
    (wd / 'README.md').write_text(INITIAL_README, encoding='utf-8')
    shutil.copy(FIXTURES / 'task_description.md', wd / 'task_description.md')
    # 初始化 git 仓库（让 git log 可用）。子仓库必须局部关闭 autocrlf/safecrlf，
    # 否则继承 Windows 父项目的 core.autocrlf=true 会对 LF 文件反复报警告。
    try:
        subprocess.run(['git', 'init', '-q'], cwd=wd, check=True)
        subprocess.run(['git', 'config', 'core.autocrlf', 'false'], cwd=wd, check=True)
        subprocess.run(['git', 'config', 'core.safecrlf', 'false'], cwd=wd, check=True)
        subprocess.run(['git', 'add', '.'], cwd=wd, check=True)
        subprocess.run(['git', 'commit', '-q', '-m', 'initial'], cwd=wd,
                       env={**os.environ, 'GIT_AUTHOR_NAME': 'exp5',
                            'GIT_AUTHOR_EMAIL': 'exp5@local',
                            'GIT_COMMITTER_NAME': 'exp5',
                            'GIT_COMMITTER_EMAIL': 'exp5@local'}, check=True)
    except Exception:
        pass
    return wd


def run_trial(variant: str, seed: int) -> TrialResult:
    wd = prepare_workdir(variant, seed)
    task = (FIXTURES / 'task_description.md').read_text(encoding='utf-8')

    mc = ModelConfig.from_env()
    mc.temperature = 0.1 + (seed % 10) * 0.01

    # 阶段 A：跑到第 5 步附近就用 max_iterations 截断
    ac_a = AgentConfig(
        cwd=wd, max_iterations=25, planning_turns=2,
        allow_shell=True, allow_destructive=False,
    )

    t0 = time.time()
    result_a = None
    try:
        result_a = run(task, model_config=mc, agent_config=ac_a)
    except Exception as exc:
        print(f'  阶段 A 异常: {exc}')

    phase_a_done = _parse_done_steps(wd)
    phase_a_done_count = len(phase_a_done)
    # 读取 session
    session_dir = wd / '.harness_sessions'
    sessions_after_a = sorted(session_dir.glob('*.jsonl'),
                              key=lambda p: p.stat().st_mtime) if session_dir.exists() else []
    if not sessions_after_a:
        return TrialResult(variant=variant, seed=seed, phase_a_turns=0, phase_b_turns=0,
                           wrong_dir_errors=0, repeated_step_attempts=0,
                           stale_file_assumptions=0, first_productive_turn=-1,
                           phase_a_done_count=phase_a_done_count,
                           phase_b_done_count=phase_a_done_count,
                           incremental_steps=0,
                           final_completed_steps=phase_a_done_count,
                           wall_seconds=time.time() - t0)

    session_a_id = sessions_after_a[0].stem
    messages_a = load_session_messages(session_a_id, session_dir)
    phase_a_turns = result_a.turns if result_a else len(messages_a)
    # 记下 Phase A 结束时已存在的 session 文件集合，Phase B 会新增一个
    sessions_before_b = {p.name for p in sessions_after_a}

    # 阶段 B：恢复执行
    resume_prompt = PLAIN_PROMPT if variant == 'plain' else THREE_STEP_PROMPT
    ac_b = AgentConfig(
        cwd=wd, max_iterations=20, planning_turns=0,
        allow_shell=True, allow_destructive=False,
    )

    result_b = None
    try:
        result_b = resume(session_a_id, prompt=resume_prompt,
                          model_config=mc, agent_config=ac_b)
    except Exception as exc:
        print(f'  阶段 B 异常: {exc}')

    # 定位 Phase B 自己的 session 文件（resume() 会创建新的 session_id）
    sessions_after_b = sorted(session_dir.glob('*.jsonl'),
                              key=lambda p: p.stat().st_mtime)
    new_sessions = [p for p in sessions_after_b if p.name not in sessions_before_b]
    if new_sessions:
        session_b_id = new_sessions[-1].stem
        messages_b = load_session_messages(session_b_id, session_dir)
    else:
        messages_b = []

    wrong_dir = count_wrong_dir_errors(messages_b)
    repeated = count_repeated_steps(messages_b, phase_a_done)
    first_prod = find_first_productive_turn(messages_b, phase_a_done)
    phase_b_done_count = count_completed_steps(wd)
    incremental = phase_b_done_count - phase_a_done_count

    return TrialResult(
        variant=variant, seed=seed,
        phase_a_turns=phase_a_turns,
        phase_b_turns=result_b.turns if result_b else 0,
        wrong_dir_errors=wrong_dir,
        repeated_step_attempts=repeated,
        stale_file_assumptions=0,  # 需要更复杂的启发式，暂留 0
        first_productive_turn=first_prod,
        phase_a_done_count=phase_a_done_count,
        phase_b_done_count=phase_b_done_count,
        incremental_steps=incremental,
        final_completed_steps=phase_b_done_count,
        wall_seconds=time.time() - t0,
    )


def _parse_done_steps(workdir: Path) -> set[int]:
    task_md = workdir / 'TASK.md'
    if not task_md.exists():
        return set()
    text = task_md.read_text(encoding='utf-8', errors='ignore')
    return set(int(m.group(1)) for m in STEP_DONE_RE.finditer(text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--seeds', type=int, nargs='+', default=None)
    args = ap.parse_args()

    if args.smoke:
        seeds = args.seeds or [42, 7]
    else:
        seeds = args.seeds or [42, 7, 123, 2024, 99, 11, 33, 77]

    if not os.environ.get('HARNESS_API_KEY') and not os.environ.get('OPENAI_API_KEY'):
        print('ERROR: 未设置 API key')
        sys.exit(2)

    out = RESULTS / 'raw.jsonl'
    idx = 0
    total = len(seeds) * 2
    with out.open('w', encoding='utf-8') as f:
        for variant in ['plain', 'three_step']:
            for seed in seeds:
                idx += 1
                print(f'[{idx}/{total}] variant={variant} seed={seed}')
                r = run_trial(variant, seed)
                f.write(json.dumps(asdict(r), ensure_ascii=False) + '\n')
                f.flush()
                print(f'  -> phase_a_done={r.phase_a_done_count}, '
                      f'phase_b_done={r.phase_b_done_count}, '
                      f'incr={r.incremental_steps}, '
                      f'wrong_dir={r.wrong_dir_errors}, '
                      f'repeated={r.repeated_step_attempts}, '
                      f'first_prod={r.first_productive_turn}')

    print(f'\n原始数据已写入 {out}')


if __name__ == '__main__':
    main()
