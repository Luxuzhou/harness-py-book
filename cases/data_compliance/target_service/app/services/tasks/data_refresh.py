"""
数据刷新任务。

定期从外部数据源（生产系统是 ClickHouse，本案例是 CSV 文件）
拉取最新数据，批量灌入 Repository。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.lab_result_repository import LabResultRepository
from app.repositories.patient_repository import PatientRepository
from app.services.data_processor import DataProcessor

logger = logging.getLogger(__name__)


@dataclass
class DataRefreshConfig:
    """刷新任务配置。"""
    data_dir: Path = Path('sample_data')
    refresh_patients: bool = True
    refresh_lab_results: bool = True
    refresh_instruments: bool = True
    full_reload: bool = False  # True=清空后全量；False=增量
    max_rows_per_file: int = 100_000


class DataRefreshTask:
    """
    数据刷新任务。

    run() 返回本次刷新的摘要，包括每个数据集的加载行数。
    """

    def __init__(
        self,
        patient_repo: PatientRepository,
        lab_repo: LabResultRepository,
        instrument_repo: InstrumentRepository,
        config: Optional[DataRefreshConfig] = None,
        data_processor: Optional[DataProcessor] = None,
    ):
        self.patient_repo = patient_repo
        self.lab_repo = lab_repo
        self.instrument_repo = instrument_repo
        self.config = config or DataRefreshConfig()
        self.data_processor = data_processor or DataProcessor()
        self._last_summary: Optional[Dict[str, Any]] = None
        self._run_count = 0

    def run(self) -> Dict[str, Any]:
        start = time.time()
        self._run_count += 1
        data_path = self.config.data_dir
        summary: Dict[str, Any] = {
            'run_at': datetime.now().isoformat(),
            'run_index': self._run_count,
            'data_dir': str(data_path),
            'full_reload': self.config.full_reload,
            'patients': {},
            'lab_results': {},
            'instruments': {},
        }

        if self.config.refresh_patients:
            summary['patients'] = self._refresh_patients(data_path)
        if self.config.refresh_lab_results:
            summary['lab_results'] = self._refresh_lab_results(data_path)
        if self.config.refresh_instruments:
            summary['instruments'] = self._refresh_instruments(data_path)

        summary['duration_seconds'] = round(time.time() - start, 3)
        self._last_summary = summary
        logger.info('data refresh #%d done: %s', self._run_count, summary)
        return summary

    def _refresh_patients(self, data_path: Path) -> Dict[str, Any]:
        csv_path = data_path / 'patients.csv'
        if not csv_path.exists():
            return {'skipped': True, 'reason': 'file_missing'}
        records = self.data_processor.load_patients_csv(str(csv_path))
        if self.config.full_reload:
            self._truncate(self.patient_repo)
        loaded = self.patient_repo.load_from_records(
            records[:self.config.max_rows_per_file]
        )
        return {'loaded': loaded, 'source': str(csv_path),
                'total_seen': len(records)}

    def _refresh_lab_results(self, data_path: Path) -> Dict[str, Any]:
        csv_path = data_path / 'lab_results.csv'
        if not csv_path.exists():
            return {'skipped': True, 'reason': 'file_missing'}
        records = self.data_processor.load_lab_results_csv(str(csv_path))
        if self.config.full_reload:
            self._truncate(self.lab_repo)
        loaded = self.lab_repo.load_from_records(
            records[:self.config.max_rows_per_file]
        )
        return {'loaded': loaded, 'source': str(csv_path),
                'total_seen': len(records)}

    def _refresh_instruments(self, data_path: Path) -> Dict[str, Any]:
        csv_path = data_path / 'instruments.csv'
        if not csv_path.exists():
            return {'skipped': True, 'reason': 'file_missing'}
        records = self.data_processor.load_instruments_csv(str(csv_path))
        if self.config.full_reload:
            self._truncate(self.instrument_repo)
        loaded = self.instrument_repo.load_from_records(
            records[:self.config.max_rows_per_file]
        )
        return {'loaded': loaded, 'source': str(csv_path),
                'total_seen': len(records)}

    @staticmethod
    def _truncate(repo: Any) -> None:
        if hasattr(repo, '_store'):
            with getattr(repo, '_lock', None) or _dummy_lock():
                repo._store.clear()
                repo._indexes = {f: {} for f in repo._indexes}

    def last_summary(self) -> Optional[Dict[str, Any]]:
        return self._last_summary

    def run_count(self) -> int:
        return self._run_count


class _dummy_lock:
    def __enter__(self): return self
    def __exit__(self, *a): return False
