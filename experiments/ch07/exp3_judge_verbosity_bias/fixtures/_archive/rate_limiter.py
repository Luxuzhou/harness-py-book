"""固定窗口限流器。"""
import time


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: list[float] = []

    def _clean_expired(self) -> None:
        now = time.time()
        self._calls = [t for t in self._calls if now - t < self.window]

    def _is_rate_limited(self) -> bool:
        self._clean_expired()
        return len(self._calls) > self.max_calls  # bug: 应该是 >=

    def check(self) -> bool:
        """返回 True 表示允许调用，False 表示被限流。"""
        if self._is_rate_limited():
            return False
        self._calls.append(time.time())
        return True
