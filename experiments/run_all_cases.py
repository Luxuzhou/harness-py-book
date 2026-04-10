"""
三案例全量实验 — 自动运行 + 捕获结果
======================================
用法: python experiments/run_all_cases.py
需要: .env 中的 OPENAI_API_KEY 或 HARNESS_API_KEY

每个案例的运行日志、验证结果、运行指标自动保存到
experiments/results/ 目录下，作为书稿写作素材。
"""

import io
import json
import os
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# 加载 .env
env_file = ROOT / '.env'
if env_file.exists():
    for line in env_file.read_text(encoding='utf-8').splitlines():
        if line.strip() and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

RESULTS_DIR = ROOT / 'experiments' / 'results'
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def capture_run(name: str, run_fn, verify_fn=None) -> dict:
    """运行一个案例，捕获全部输出和指标。"""
    print(f'\n{"#"*60}')
    print(f'# {name}')
    print(f'# {datetime.now().isoformat()}')
    print(f'{"#"*60}\n')

    record = {
        'name': name,
        'start_time': datetime.now().isoformat(),
        'run_output': '',
        'run_error': '',
        'verify_output': '',
        'verify_error': '',
        'run_result': None,
        'verify_passed': None,
        'duration_seconds': 0,
        'exception': None,
    }

    # 运行
    t0 = time.time()
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        # 同时打印到控制台和捕获
        class TeeWriter:
            def __init__(self, original, buffer):
                self.original = original
                self.buffer = buffer
            def write(self, s):
                self.original.write(s)
                self.buffer.write(s)
            def flush(self):
                self.original.flush()
                self.buffer.flush()

        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout = TeeWriter(old_stdout, stdout_buf)
        sys.stderr = TeeWriter(old_stderr, stderr_buf)

        result = run_fn()
        record['run_result'] = _serialize_result(result)

    except Exception as e:
        record['exception'] = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
        print(f'[ERROR] {name} 运行异常: {e}')
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    record['run_output'] = stdout_buf.getvalue()
    record['run_error'] = stderr_buf.getvalue()
    record['duration_seconds'] = round(time.time() - t0, 1)
    record['end_time'] = datetime.now().isoformat()

    # 验证
    if verify_fn:
        v_stdout = io.StringIO()
        v_stderr = io.StringIO()
        try:
            sys.stdout = TeeWriter(old_stdout, v_stdout)
            sys.stderr = TeeWriter(old_stderr, v_stderr)
            verify_passed = verify_fn()
            record['verify_passed'] = verify_passed
        except Exception as e:
            record['verify_error'] = f'{type(e).__name__}: {e}'
            print(f'[ERROR] {name} 验证异常: {e}')
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
        record['verify_output'] = v_stdout.getvalue()

    # 保存
    safe_name = name.replace(' ', '_').replace(':', '')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = RESULTS_DIR / f'{safe_name}_{ts}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n[SAVED] {out_path}')

    # 同时保存纯文本日志（方便引用到书稿）
    log_path = RESULTS_DIR / f'{safe_name}_{ts}.log'
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f'=== {name} ===\n')
        f.write(f'时间: {record["start_time"]} - {record.get("end_time", "")}\n')
        f.write(f'耗时: {record["duration_seconds"]}s\n\n')
        f.write('--- 运行输出 ---\n')
        f.write(record['run_output'])
        if record['run_error']:
            f.write('\n--- 错误输出 ---\n')
            f.write(record['run_error'])
        if record['verify_output']:
            f.write('\n--- 验证输出 ---\n')
            f.write(record['verify_output'])
        if record['exception']:
            f.write('\n--- 异常 ---\n')
            f.write(record['exception'])
    print(f'[SAVED] {log_path}')

    return record


def _serialize_result(result) -> dict | None:
    """将RunResult/SwarmResult序列化为dict。"""
    if result is None:
        return None
    if hasattr(result, '__dict__'):
        d = {}
        for k, v in result.__dict__.items():
            try:
                json.dumps(v)
                d[k] = v
            except (TypeError, ValueError):
                d[k] = str(v)
        return d
    return str(result)


# ============ Case 1: 遗留系统重构 ============

def run_case1():
    import tempfile
    tmp = tempfile.mkdtemp()
    os.environ['INVENTORY_DB'] = os.path.join(tmp, 'inventory.db')

    from harness_py_pro import run, ModelConfig, AgentConfig
    task = (ROOT / 'cases' / 'refactor' / 'TASK.md').read_text(encoding='utf-8')
    target_dir = ROOT / 'cases' / 'refactor' / 'target_project'

    return run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=target_dir,
            max_iterations=40,
            planning_turns=3,
            allow_write=True,
            allow_shell=True,
        ),
    )


def verify_case1():
    sys.path.insert(0, str(ROOT / 'cases' / 'refactor'))
    import importlib
    spec = importlib.util.spec_from_file_location('verify', ROOT / 'cases' / 'refactor' / 'verify.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


# ============ Case 2: 医疗数据分析 ============

def run_case2():
    from harness_py_pro import run, ModelConfig, AgentConfig
    from harness_py_pro.config import HookConfig

    sys.path.insert(0, str(ROOT / 'cases' / 'medical'))
    from compliance_hooks import pre_tool_hook, post_tool_hook

    task = (ROOT / 'cases' / 'medical' / 'TASK.md').read_text(encoding='utf-8')
    case_dir = ROOT / 'cases' / 'medical'

    return run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=case_dir,
            max_iterations=30,
            planning_turns=2,
            allow_write=True,
            allow_shell=True,
            network_isolated=True,
            allowed_paths=['sample_data', '.'],
            hooks=HookConfig(
                pre_tool=pre_tool_hook,
                post_tool=post_tool_hook,
            ),
        ),
    )


def verify_case2():
    spec = __import__('importlib').util.spec_from_file_location('verify', ROOT / 'cases' / 'medical' / 'verify.py')
    mod = __import__('importlib').util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


# ============ Case 3: 多Agent全栈 ============

def run_case3():
    from harness_py_pro import ModelConfig
    from harness_py_pro.swarm import orchestrate, AgentRole
    import re

    case_dir = ROOT / 'cases' / 'fullstack'
    (case_dir / 'output').mkdir(exist_ok=True)

    task = (case_dir / 'TASK.md').read_text(encoding='utf-8')
    planner_prompt = (case_dir / 'roles' / 'planner.md').read_text(encoding='utf-8')
    generator_prompt = (case_dir / 'roles' / 'generator.md').read_text(encoding='utf-8')
    evaluator_prompt = (case_dir / 'roles' / 'evaluator.md').read_text(encoding='utf-8')

    roles = [
        AgentRole(
            name='Planner',
            role_prompt=planner_prompt,
            tool_filter=['read_file', 'grep_search', 'glob_search', 'write_file'],
            max_iterations=10, planning_turns=1, allow_shell=False,
        ),
        AgentRole(
            name='Generator',
            role_prompt=generator_prompt,
            tool_filter=['read_file', 'write_file', 'edit_file', 'bash', 'grep_search', 'glob_search'],
            max_iterations=20, planning_turns=2,
        ),
        AgentRole(
            name='Evaluator',
            role_prompt=evaluator_prompt,
            tool_filter=['read_file', 'grep_search', 'glob_search', 'bash', 'write_file'],
            max_iterations=12, planning_turns=1, allow_write=True,
        ),
    ]

    def convergence_check(round_num, work_dir):
        review_file = work_dir / 'output' / 'review.md'
        if not review_file.exists():
            return False, ''
        content = review_file.read_text(encoding='utf-8')
        if 'PASS' in content.upper() and '判定' in content:
            score_match = re.search(r'(\d+)\s*/\s*100', content)
            score = int(score_match.group(1)) if score_match else 0
            if score >= 70:
                return True, f'Evaluator评分 {score}/100 >= 70, PASS'
        return False, ''

    return orchestrate(
        task, roles,
        model_config=ModelConfig.from_env(),
        cwd=case_dir,
        max_rounds=3,
        convergence_check=convergence_check,
    )


def verify_case3():
    spec = __import__('importlib').util.spec_from_file_location('verify', ROOT / 'cases' / 'fullstack' / 'verify.py')
    mod = __import__('importlib').util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


# ============ Main ============

def main():
    print('='*60)
    print('Harness-py Book — 三案例全量实验')
    print(f'时间: {datetime.now().isoformat()}')
    print(f'结果目录: {RESULTS_DIR}')
    print('='*60)

    # 检查API key
    api_key = os.getenv('HARNESS_API_KEY', os.getenv('OPENAI_API_KEY', ''))
    if not api_key:
        print('[FATAL] 未配置API key。请在 .env 中设置 OPENAI_API_KEY 或 HARNESS_API_KEY')
        sys.exit(1)
    print(f'API Key: ...{api_key[-8:]}')
    print(f'Model: {os.getenv("HARNESS_MODEL", os.getenv("MODEL", "deepseek-chat"))}')
    print()

    cases = [
        ('Case1_Refactor', run_case1, verify_case1),
        ('Case2_Medical', run_case2, verify_case2),
        ('Case3_Fullstack', run_case3, verify_case3),
    ]

    summary = []
    for name, run_fn, verify_fn in cases:
        record = capture_run(name, run_fn, verify_fn)
        summary.append({
            'name': name,
            'duration': record['duration_seconds'],
            'turns': record.get('run_result', {}).get('turns', '?') if record.get('run_result') else '?',
            'tool_calls': record.get('run_result', {}).get('tool_calls', '?') if record.get('run_result') else '?',
            'tokens': record.get('run_result', {}).get('total_tokens', '?') if record.get('run_result') else '?',
            'cost': record.get('run_result', {}).get('cost_usd', '?') if record.get('run_result') else '?',
            'verify': record.get('verify_passed', '?'),
            'error': record.get('exception', '')[:100] if record.get('exception') else '',
        })
        print()

    # 汇总
    print('\n' + '='*60)
    print('实验汇总')
    print('='*60)
    for s in summary:
        status = 'PASS' if s['verify'] else ('FAIL' if s['verify'] is False else 'N/A')
        error = f' [{s["error"]}]' if s['error'] else ''
        print(f'  {s["name"]}: {s["duration"]}s, {s["turns"]} turns, '
              f'{s["tool_calls"]} tools, {s["tokens"]} tokens, '
              f'${s["cost"]}, verify={status}{error}')

    # 保存汇总
    summary_path = RESULTS_DIR / f'summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n[SAVED] {summary_path}')


if __name__ == '__main__':
    main()
