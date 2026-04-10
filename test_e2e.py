"""端到端测试：验证harness_py完整流程。"""
import os
import sys
from pathlib import Path

# 加载.env
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip())

from harness_py.agent import run
from harness_py.config import ModelConfig, AgentConfig

def test_simple_task():
    """测试1：简单的文件读取任务。"""
    print('=== Test 1: 简单文件读取 ===')
    mc = ModelConfig.from_env()
    ac = AgentConfig(cwd=Path(__file__).parent, max_iterations=5, allow_write=False, allow_shell=False)

    result = run('请读取 test_e2e.py 文件的前10行，告诉我这个文件是做什么的。', model_config=mc, agent_config=ac)

    print(f'  turns={result.turns} tools={result.tool_calls} stop={result.stop_reason}')
    print(f'  output: {result.output[:100]}...' if result.output else '  output: (empty)')

    assert result.turns > 0, 'Should have at least 1 turn'
    assert result.tool_calls >= 1, 'Should have called read_file'
    assert result.stop_reason == 'stop', f'Should stop naturally, got {result.stop_reason}'
    print('  PASSED\n')


def test_bash_tool():
    """测试2：bash工具执行。"""
    print('=== Test 2: Bash工具 ===')
    mc = ModelConfig.from_env()
    ac = AgentConfig(cwd=Path(__file__).parent, max_iterations=5, allow_shell=True, allow_write=False)

    result = run('请执行 echo hello_from_harness_py 命令，告诉我输出。', model_config=mc, agent_config=ac)

    print(f'  turns={result.turns} tools={result.tool_calls} stop={result.stop_reason}')
    assert result.tool_calls >= 1, 'Should have called bash'
    print('  PASSED\n')


def test_session_persistence():
    """测试3：jsonl session写入。"""
    print('=== Test 3: Session持久化 ===')
    mc = ModelConfig.from_env()
    ac = AgentConfig(cwd=Path(__file__).parent, max_iterations=3, allow_write=False, allow_shell=False)

    result = run('请列出当前目录下的.py文件。', model_config=mc, agent_config=ac)

    # 检查jsonl是否生成
    session_dir = Path(__file__).parent / '.harness_sessions'
    jsonl_files = list(session_dir.glob('*.jsonl'))
    assert len(jsonl_files) > 0, 'Should have created jsonl session file'

    latest = max(jsonl_files, key=lambda p: p.stat().st_mtime)
    lines = latest.read_text(encoding='utf-8').strip().split('\n')
    print(f'  session={latest.stem[:12]}... events={len(lines)}')
    assert len(lines) >= 3, 'Should have at least 3 events (permission-mode + system + user)'

    # 检查格式
    import json
    first = json.loads(lines[0])
    assert first.get('type') == 'permission-mode', f'First event should be permission-mode, got {first.get("type")}'
    print('  PASSED\n')


if __name__ == '__main__':
    print('Harness-py 端到端测试\n')

    try:
        test_simple_task()
        test_bash_tool()
        test_session_persistence()
        print('All tests PASSED')
    except Exception as e:
        print(f'FAILED: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
