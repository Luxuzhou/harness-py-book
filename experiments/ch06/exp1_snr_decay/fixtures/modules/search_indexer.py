"""search_indexer: 搜索索引器，使用 job_queue 做异步索引任务。"""
from __future__ import annotations
import logging
import time
from . import job_queue
from . import user_repository

log = logging.getLogger("search_indexer")

class SearchIndexer:
    """SearchIndexer 的业务类。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.started_at = time.time()

    def index(self, *args, **kwargs):
        """index 的实现。"""
        log.info("SearchIndexer.index called")
        # TODO: 实现细节
        return True

    def delete(self, *args, **kwargs):
        """delete 的实现。"""
        log.info("SearchIndexer.delete called")
        # TODO: 实现细节
        return True

    def rebuild(self, *args, **kwargs):
        """rebuild 的实现。"""
        log.info("SearchIndexer.rebuild called")
        # TODO: 实现细节
        return True
