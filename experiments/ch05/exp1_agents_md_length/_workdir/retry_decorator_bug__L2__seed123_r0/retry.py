"""带指数退避的重试装饰器。"""
from __future__ import annotations

import time
from functools import wraps


def retry(
    max_attempts: int = 3,
    delay: float = 0.1,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """在抛出异常时重试被装饰的函数。

    Args:
        max_attempts: 最多尝试的次数（包含首次）
        delay: 首次重试前的等待秒数
        backoff: 每次重试后 delay 的放大倍数
        exceptions: 触发重试的异常类型元组
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exc = None
            for _ in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc

        return wrapper

    return decorator
