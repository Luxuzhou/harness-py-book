"""email_sender: 邮件发送器，依赖 template_engine 和 config_loader。"""
from __future__ import annotations
import logging
import time
from . import template_engine
from . import config_loader

log = logging.getLogger("email_sender")

class EmailSender:
    """EmailSender 的业务类。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.started_at = time.time()

    def send(self, *args, **kwargs):
        """send 的实现。"""
        log.info("EmailSender.send called")
        # TODO: 实现细节
        return True

    def send_batch(self, *args, **kwargs):
        """send_batch 的实现。"""
        log.info("EmailSender.send_batch called")
        # TODO: 实现细节
        return True

    def retry_failed(self, *args, **kwargs):
        """retry_failed 的实现。"""
        log.info("EmailSender.retry_failed called")
        # TODO: 实现细节
        return True
