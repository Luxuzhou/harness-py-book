"""验证 5 步集成任务是否完成。每个 case 对应一步。"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))


def _reload(module_name: str):
    if module_name in sys.modules:
        del sys.modules[module_name]
    return importlib.import_module(module_name)


def test_step1_summary_method_exists():
    """第 1 步：CostTracker 有 summary 方法，返回三个键。"""
    ct = _reload('cost_tracker')
    tracker = ct.CostTracker()
    tracker.record('input', 1000)
    tracker.record('output', 500)
    result = tracker.summary()
    assert isinstance(result, dict), 'summary 必须返回 dict'
    for key in ('total_input_tokens', 'total_output_tokens', 'total_cost_usd'):
        assert key in result, f'summary 缺少 {key}'
    assert result['total_input_tokens'] == 1000
    assert result['total_output_tokens'] == 500


def test_step2_runtime_imports_tracker():
    """第 2 步：AgentRuntime 导入并实例化 CostTracker。"""
    rt = _reload('agent_runtime')
    agent = rt.AgentRuntime()
    assert hasattr(agent, 'tracker'), 'AgentRuntime 必须有 tracker 属性'
    ct = _reload('cost_tracker')
    assert isinstance(agent.tracker, ct.CostTracker)


def test_step3_step_records_tokens():
    """第 3 步：step() 调用后 tracker 记录了 input 和 output token。"""
    rt = _reload('agent_runtime')
    agent = rt.AgentRuntime()
    agent.step('hello')
    summary = agent.tracker.summary()
    assert summary['total_input_tokens'] > 0, 'tracker 应记录 input'
    assert summary['total_output_tokens'] > 0, 'tracker 应记录 output'


def test_step4_shutdown_prints_summary(capsys):
    """第 4 步：shutdown 打印 json 格式的 summary。"""
    rt = _reload('agent_runtime')
    agent = rt.AgentRuntime()
    agent.step('hello')
    agent.shutdown()
    captured = capsys.readouterr()
    out = captured.out.strip()
    assert out, 'shutdown 必须打印 summary'
    data = json.loads(out)
    assert 'total_input_tokens' in data


def test_step5_readme_has_cost_tracking_section():
    """第 5 步：README.md 含 Cost Tracking 段落。"""
    readme = HERE / 'README.md'
    assert readme.exists(), '需要 README.md'
    text = readme.read_text(encoding='utf-8')
    assert '## Cost Tracking' in text, 'README 必须包含 ## Cost Tracking 段落'
