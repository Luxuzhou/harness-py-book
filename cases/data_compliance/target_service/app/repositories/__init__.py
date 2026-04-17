"""
Repository 层：封装数据访问，对上层服务屏蔽存储细节。

当前案例阶段用内存 dict + CSV 加载做持久化模拟。
生产场景可以在不改上层的前提下替换为 ClickHouse / PostgreSQL。
"""

from app.repositories.base import BaseRepository, Pagination, SortSpec
from app.repositories.patient_repository import PatientRepository
from app.repositories.lab_result_repository import LabResultRepository
from app.repositories.instrument_repository import InstrumentRepository
from app.repositories.anomaly_repository import AnomalyRepository
from app.repositories.audit_repository import AuditRepository

__all__ = [
    'BaseRepository',
    'Pagination',
    'SortSpec',
    'PatientRepository',
    'LabResultRepository',
    'InstrumentRepository',
    'AnomalyRepository',
    'AuditRepository',
]
