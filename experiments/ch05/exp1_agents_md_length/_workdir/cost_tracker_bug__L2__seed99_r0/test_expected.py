"""CostTracker.summary()的预期行为。Agent需要让这些测试通过。"""
import pytest

from cost_tracker import CostTracker


def test_summary_returns_dict_with_sums():
    t = CostTracker()
    t.record('input', 100)
    t.record('output', 50)
    t.record('input', 30)
    s = t.summary()
    assert s == {'input': 130, 'output': 50}


def test_summary_empty_tracker_returns_empty_dict():
    t = CostTracker()
    assert t.summary() == {}


def test_summary_does_not_expose_internal_state():
    t = CostTracker()
    t.record('input', 10)
    s = t.summary()
    s['input'] = 999
    assert t.summary() == {'input': 10}, 'summary() 返回的字典被修改后不应影响内部状态'


def test_record_rejects_negative():
    t = CostTracker()
    with pytest.raises(ValueError):
        t.record('input', -1)
