"""log_aggregator 的预期行为。"""
from log_aggregator import aggregate


def test_single_line():
    lines = ['{"ts": "2026-04-27T10:30:00", "level": "INFO", "msg": "x"}']
    assert aggregate(lines) == {'INFO': {'2026-04-27 10:00': 1}}


def test_two_levels():
    lines = [
        '{"ts": "2026-04-27T10:30:00", "level": "INFO", "msg": "x"}',
        '{"ts": "2026-04-27T10:45:00", "level": "ERROR", "msg": "y"}',
    ]
    assert aggregate(lines) == {
        'INFO': {'2026-04-27 10:00': 1},
        'ERROR': {'2026-04-27 10:00': 1},
    }


def test_same_hour_aggregation():
    lines = [
        '{"ts": "2026-04-27T10:00:00", "level": "INFO", "msg": "a"}',
        '{"ts": "2026-04-27T10:59:00", "level": "INFO", "msg": "b"}',
    ]
    assert aggregate(lines) == {'INFO': {'2026-04-27 10:00': 2}}


def test_empty():
    assert aggregate([]) == {}
