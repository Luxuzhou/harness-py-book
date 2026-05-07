"""RateLimiter 的预期行为。"""
from rate_limiter import RateLimiter


def test_allow_within_limit():
    rl = RateLimiter(max_calls=3, window_seconds=10)
    assert rl.check() is True
    assert rl.check() is True
    assert rl.check() is True


def test_block_at_exactly_limit():
    """第 max_calls + 1 次调用应该被拒绝（超过 max 即拒）。"""
    rl = RateLimiter(max_calls=3, window_seconds=10)
    rl.check()
    rl.check()
    rl.check()
    assert rl.check() is False  # 第 4 次应拒绝（已经 3 次了）


def test_one_call_under_limit_works():
    rl = RateLimiter(max_calls=1, window_seconds=10)
    assert rl.check() is True
    assert rl.check() is False  # 第 2 次拒绝
