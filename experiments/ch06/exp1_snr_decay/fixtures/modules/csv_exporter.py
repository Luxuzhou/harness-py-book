"""csv_exporter: CSV 导出，依赖 data_validator 做字段校验。"""
from __future__ import annotations
import logging
import time
from . import data_validator

log = logging.getLogger("csv_exporter")

class CsvExporter:
    """CsvExporter 的业务类。"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.started_at = time.time()

    def export(self, *args, **kwargs):
        """export 的实现。"""
        log.info("CsvExporter.export called")
        # TODO: 实现细节
        return True

    def export_streamed(self, *args, **kwargs):
        """export_streamed 的实现。"""
        log.info("CsvExporter.export_streamed called")
        # TODO: 实现细节
        return True
