"""
配置热重载
==========
监控settings文件mtime变化，自动重载hook配置。
对标OpenHarness hooks/hot_reload.py。

设计思路：
  不用watchdog等第三方库，直接比较文件mtime。
  调用方在主循环中定期调用 ``check()``，
  如果文件修改时间变了，触发 ``on_change`` 回调。

典型用法::

    watcher = ConfigWatcher(Path('settings.json'), on_change=reload_hooks)
    # 在主循环中定期调用
    while running:
        watcher.check()
        time.sleep(1)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


class ConfigWatcher:
    """配置文件变更监控器。

    监控单个文件的 ``st_mtime``。当检测到变化时，
    立即执行 ``on_change`` 回调并返回 ``True``。

    Usage::

        watcher = ConfigWatcher(
            config_path=Path('settings.json'),
            on_change=reload_hooks,
        )
        # 在主循环或定时器中反复调用
        changed = watcher.check()
    """

    def __init__(
        self,
        config_path: Path,
        on_change: Callable[[], None],
    ):
        self._path = Path(config_path)
        self._on_change = on_change
        self._last_mtime: float = 0.0
        self._update_mtime()

    # -- 公开接口 --------------------------------------------------------------

    def check(self) -> bool:
        """检查文件是否变化。如果变化了，触发回调并返回True。

        文件不存在时静默返回False（不抛异常）。

        Returns:
            True 表示检测到变化并已触发回调, False 表示无变化。
        """
        try:
            current = self._path.stat().st_mtime
        except OSError:
            return False

        if current != self._last_mtime:
            self._last_mtime = current
            self._on_change()
            return True

        return False

    @property
    def path(self) -> Path:
        """被监控的配置文件路径。"""
        return self._path

    @property
    def last_mtime(self) -> float:
        """上次记录的文件修改时间。"""
        return self._last_mtime

    # -- 内部方法 --------------------------------------------------------------

    def _update_mtime(self):
        """读取并缓存当前文件的mtime。"""
        try:
            self._last_mtime = self._path.stat().st_mtime
        except OSError:
            self._last_mtime = 0.0


class MultiConfigWatcher:
    """多配置文件监控器。

    同时监控多个配置文件，任何一个变化都触发回调。
    适用于需要同时监控 ``settings.json``、``hooks.yaml``
    等多个配置文件的场景。

    Usage::

        watcher = MultiConfigWatcher(
            config_paths=[
                Path('settings.json'),
                Path('hooks.yaml'),
            ],
            on_change=reload_all_configs,
        )
        watcher.check()  # 返回变化的文件列表
    """

    def __init__(
        self,
        config_paths: list[Path],
        on_change: Callable[[list[Path]], None],
    ):
        self._paths = [Path(p) for p in config_paths]
        self._on_change = on_change
        self._mtimes: dict[str, float] = {}
        for p in self._paths:
            self._mtimes[str(p)] = self._get_mtime(p)

    def check(self) -> list[Path]:
        """检查所有文件。返回本次变化的文件路径列表。

        如果有变化，触发 ``on_change(changed_paths)`` 回调。
        """
        changed: list[Path] = []

        for p in self._paths:
            key = str(p)
            current = self._get_mtime(p)
            if current != self._mtimes.get(key, 0.0):
                self._mtimes[key] = current
                changed.append(p)

        if changed:
            self._on_change(changed)

        return changed

    def add(self, config_path: Path):
        """动态添加一个监控文件。"""
        p = Path(config_path)
        if p not in self._paths:
            self._paths.append(p)
            self._mtimes[str(p)] = self._get_mtime(p)

    def remove(self, config_path: Path):
        """移除一个监控文件。"""
        p = Path(config_path)
        if p in self._paths:
            self._paths.remove(p)
            self._mtimes.pop(str(p), None)

    @staticmethod
    def _get_mtime(path: Path) -> float:
        """安全读取mtime。"""
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0
