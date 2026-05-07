"""session_store: 会话存储，基于 cache_client。被 auth_service 使用。"""
from __future__ import annotations
import logging
import time
from . import cache_client

log = logging.getLogger("session_store")

class SessionStore:
    """SessionStore 的业务类。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.started_at = time.time()

    def create_session(self, *args, **kwargs):
        """create_session 的实现。"""
        log.info("SessionStore.create_session called")
        # TODO: 实现细节
        return True

    def get_session(self, *args, **kwargs):
        """get_session 的实现。"""
        log.info("SessionStore.get_session called")
        # TODO: 实现细节
        return True

    def destroy_session(self, *args, **kwargs):
        """destroy_session 的实现。"""
        log.info("SessionStore.destroy_session called")
        # TODO: 实现细节
        return True
