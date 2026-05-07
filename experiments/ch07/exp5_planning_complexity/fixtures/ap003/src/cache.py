"""内存缓存。"""


class Cache:
    def __init__(self) -> None:
        self._store: dict = {}

    def set(self, key: str, value) -> None:
        self._store[key] = value

    def get(self, key: str):
        return self._store[key]  # 当前找不到会 KeyError
