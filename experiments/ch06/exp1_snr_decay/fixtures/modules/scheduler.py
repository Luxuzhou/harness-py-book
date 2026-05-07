"""scheduler: Cron 风格调度器，依赖 job_queue。"""
from __future__ import annotations
import logging
import time
from . import job_queue
from . import config_loader

log = logging.getLogger("scheduler")

class Scheduler:
    """Scheduler 的业务类。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.started_at = time.time()

    def schedule(self, *args, **kwargs):
        """schedule 的实现。"""
        log.info("Scheduler.schedule called")
        # TODO: 实现细节
        return True

    def cancel(self, *args, **kwargs):
        """cancel 的实现。"""
        log.info("Scheduler.cancel called")
        # TODO: 实现细节
        return True

    def run_once(self, *args, **kwargs):
        """run_once 的实现。"""
        log.info("Scheduler.run_once called")
        # TODO: 实现细节
        return True
