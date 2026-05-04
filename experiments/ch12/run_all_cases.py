"""
三案例全量实验 — 自动运行 + 捕获结果
======================================
用法: python experiments/run_all_cases.py
需要: .env 中的 OPENAI_API_KEY 或 HARNESS_API_KEY

新版三案例（对应书稿第 8-10 章）：
- Case1  cases/refactor_enterprise   — Java 企业项目重构（Ch8）
- Case2  cases/data_compliance       — Python 医疗合规服务（Ch9）
- Case3  cases/multiagent_enterprise — 跨 Java/Python 多 Agent 编排（Ch10）

每个案例的运行日志、验证结果、运行指标自动保存到
experiments/results/ 目录下，作为书稿写作素材。

旧版三案例（refactor/medical/fullstack）已移到 cases/_archive/*_legacy/。
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


# ============ Case 1: Java 企业项目重构（Ch8） ============

def run_case1():
    from harness_py_pro import run, ModelConfig, AgentConfig
    case_dir = ROOT / 'cases' / 'refactor_enterprise'
    task = (case_dir / 'TASK.md').read_text(encoding='utf-8')
    target_dir = case_dir / 'target_project'

    return run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=target_dir,
            max_iterations=50,
            planning_turns=3,
            allow_write=True,
            allow_shell=True,
        ),
    )


def verify_case1():
    import importlib.util
    case_dir = ROOT / 'cases' / 'refactor_enterprise'
    sys.path.insert(0, str(case_dir))
    spec = importlib.util.spec_from_file_location('verify_refactor', case_dir / 'verify.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


# ============ Case 2: Python 医疗合规服务（Ch9） ============

def run_case2():
    from harness_py_pro import run, ModelConfig, AgentConfig

    case_dir = ROOT / 'cases' / 'data_compliance'
    task = (case_dir / 'TASK.md').read_text(encoding='utf-8')
    target_dir = case_dir / 'target_service'

    return run(
        task,
        model_config=ModelConfig.from_env(),
        agent_config=AgentConfig(
            cwd=target_dir,
            max_iterations=40,
            planning_turns=2,
            allow_write=True,
            allow_shell=True,
            network_isolated=True,
            allowed_paths=['.'],
        ),
    )


def verify_case2():
    import importlib.util
    case_dir = ROOT / 'cases' / 'data_compliance'
    sys.path.insert(0, str(case_dir))
    spec = importlib.util.spec_from_file_location('verify_compliance', case_dir / 'verify.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


# ============ Case 3: 跨 Java/Python 多 Agent 编排（Ch10） ============

def run_case3():
    """通过 cases/multiagent_enterprise/run.py 运行多Agent编排。"""
    import importlib.util
    case_dir = ROOT / 'cases' / 'multiagent_enterprise'
    sys.path.insert(0, str(case_dir))
    spec = importlib.util.spec_from_file_location('run_multiagent', case_dir / 'run.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main()


def verify_case3():
    import importlib.util
    case_dir = ROOT / 'cases' / 'multiagent_enterprise'
    sys.path.insert(0, str(case_dir))
    spec = importlib.util.spec_from_file_location('verify_multiagent', case_dir / 'verify.py')
    mod = importlib.util.module_from_spec(spec)
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
        ('Case1_RefactorEnterprise', run_case1, verify_case1),
        ('Case2_DataCompliance', run_case2, verify_case2),
        ('Case3_MultiagentEnterprise', run_case3, verify_case3),
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
