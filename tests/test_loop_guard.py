"""LoopGuard单元测试。"""
from harness_py.loop_guard import LoopGuard


def test_identical_calls_detected():
    g = LoopGuard(max_identical_calls=3)
    g.check('bash', {'cmd': 'echo hi'}, True, 'hello')
    g.check('bash', {'cmd': 'echo hi'}, True, 'hello')
    ok, msg = g.check('bash', {'cmd': 'echo hi'}, True, 'hello')
    assert ok and '死循环' in msg


def test_consecutive_errors():
    g = LoopGuard(max_consecutive_errors=3)
    g.check('bash', {'cmd': '1'}, False, 'err')
    g.check('bash', {'cmd': '2'}, False, 'err')
    ok, msg = g.check('bash', {'cmd': '3'}, False, 'err')
    assert ok and '失败' in msg


def test_success_resets_errors():
    g = LoopGuard(max_consecutive_errors=3)
    g.check('bash', {'cmd': '1'}, False, 'err')
    g.check('bash', {'cmd': '2'}, False, 'err')
    g.check('bash', {'cmd': '3'}, True, 'ok')  # 成功，重置
    ok, _ = g.check('bash', {'cmd': '4'}, False, 'err')
    assert not ok  # 不应介入，因为刚重置


def test_tool_streak():
    g = LoopGuard(max_same_tool_streak=3)
    g.check('bash', {'cmd': '1'}, True, 'a')
    g.check('bash', {'cmd': '2'}, True, 'b')
    ok, msg = g.check('bash', {'cmd': '3'}, True, 'c')
    assert ok and '连续' in msg


def test_different_tool_resets_streak():
    g = LoopGuard(max_same_tool_streak=3)
    g.check('bash', {'cmd': '1'}, True, 'a')
    g.check('bash', {'cmd': '2'}, True, 'b')
    g.check('read_file', {'path': 'x'}, True, 'c')  # 换了工具
    ok, _ = g.check('bash', {'cmd': '3'}, True, 'd')
    assert not ok  # streak被重置了


def test_total_limit():
    g = LoopGuard(max_total_tool_calls=5)
    for i in range(5):
        g.check(f'tool_{i}', {}, True, f'r{i}')
    ok, msg = g.check('tool_5', {}, True, 'r5')
    assert ok and '总量' in msg


def test_reset():
    g = LoopGuard(max_identical_calls=2)
    g.check('bash', {'cmd': 'x'}, True, 'y')
    g.check('bash', {'cmd': 'x'}, True, 'y')
    g.reset()
    ok, _ = g.check('bash', {'cmd': 'x'}, True, 'y')
    assert not ok  # reset后重新计数


if __name__ == '__main__':
    for name, func in list(globals().items()):
        if name.startswith('test_'):
            try:
                func()
                print(f'  PASS {name}')
            except Exception as e:
                print(f'  FAIL {name}: {e}')
