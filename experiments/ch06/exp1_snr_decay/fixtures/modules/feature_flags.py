"""feature_flags: 特性开关系统，读取 config_loader 和 cache_client。"""
from __future__ import annotations
import logging
import time
from . import config_loader
from . import cache_client

log = logging.getLogger("feature_flags")

class FeatureFlags:
    """FeatureFlags 的业务类。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.started_at = time.time()

    def is_enabled(self, *args, **kwargs):
        """is_enabled 的实现。"""
        log.info("FeatureFlags.is_enabled called")
        # TODO: 实现细节
        return True

    def variant(self, *args, **kwargs):
        """variant 的实现。"""
        log.info("FeatureFlags.variant called")
        # TODO: 实现细节
        return True

    def track_exposure(self, *args, **kwargs):
        """track_exposure 的实现。"""
        log.info("FeatureFlags.track_exposure called")
        # TODO: 实现细节
        return True
