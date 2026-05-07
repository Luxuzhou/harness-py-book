"""retry 装饰器的预期行为。修复后所有测试必须通过。"""
import pytest

from retry import retry


def test_retries_on_first_exception_type():
    attempts = []

    @retry(max_attempts=3, delay=0.01, exceptions=(ValueError, KeyError))
    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError('not yet')
        return 'ok'

    assert flaky() == 'ok'
    assert len(attempts) == 3


def test_retries_on_second_exception_type():
    """关键bug用例：元组中第二个异常类型也应触发重试。"""
    attempts = []

    @retry(max_attempts=3, delay=0.01, exceptions=(ValueError, KeyError))
    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise KeyError('missing')
        return 'ok'

    assert flaky() == 'ok'
    assert len(attempts) == 3


def test_raises_after_exhausting_attempts():
    @retry(max_attempts=2, delay=0.01, exceptions=(ValueError,))
    def always_fails():
        raise ValueError('nope')

    with pytest.raises(ValueError):
        always_fails()


def test_unrelated_exception_not_caught():
    @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
    def raises_type_error():
        raise TypeError('unrelated')

    with pytest.raises(TypeError):
        raises_type_error()
