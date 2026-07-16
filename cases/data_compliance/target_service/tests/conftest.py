"""
pytest 公共 fixture。

把服务根目录（target_service）加入 sys.path，并提供 TestClient + 常用 Repository 实例。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parent.parent
if str(TARGET_ROOT) not in sys.path:
    sys.path.insert(0, str(TARGET_ROOT))

import pytest  # noqa: E402

from app.repositories import (  # noqa: E402
    PatientRepository, LabResultRepository,
    InstrumentRepository, AnomalyRepository, AuditRepository,
)


@pytest.fixture
def patient_repo() -> PatientRepository:
    return PatientRepository()


@pytest.fixture
def lab_repo() -> LabResultRepository:
    return LabResultRepository()


@pytest.fixture
def instrument_repo() -> InstrumentRepository:
    return InstrumentRepository()


@pytest.fixture
def anomaly_repo() -> AnomalyRepository:
    return AnomalyRepository()


@pytest.fixture
def audit_repo(tmp_path) -> AuditRepository:
    return AuditRepository(log_dir=tmp_path / 'audit_logs')


@pytest.fixture
def sample_patient_records():
    return [
        {'patient_id': f'P{i:06d}', 'name': f'患者{i}',
         'id_card': f'110101199{i:02d}0101{i:04d}',
         'gender': 'male' if i % 2 else 'female',
         'age': 20 + (i % 50),
         'department': ['内科', '外科', '儿科', '急诊科'][i % 4],
         'diagnosis': '高血压' if i % 3 == 0 else '糖尿病'}
        for i in range(1, 21)
    ]


@pytest.fixture
def sample_lab_records():
    from datetime import datetime, timedelta
    base_date = datetime(2026, 1, 1)
    return [
        {
            'result_id': f'R{i:06d}',
            'patient_id': f'P{(i % 20) + 1:06d}',
            'step_code': ['TP', 'ALT', 'GLU'][i % 3],
            'step_name': ['总蛋白', '丙氨酸氨基转移酶', '葡萄糖'][i % 3],
            'value': 60 + (i % 30) + i * 0.1,
            'unit': ['g/L', 'U/L', 'mmol/L'][i % 3],
            'department_id': f'INS-{(i % 5) + 1:03d}',
            'visit_date': base_date + timedelta(hours=i),
            'flag': 'N' if i % 5 else 'H',
        }
        for i in range(1, 51)
    ]


@pytest.fixture
def sample_instrument_records():
    from datetime import date, timedelta
    today = date.today()
    return [
        {
            'department_id': f'INS-{i:03d}',
            'name': f'Instrument{i}',
            'manufacturer': ['Roche', 'Beckman', 'Mindray'][i % 3],
            'model': f'Model-{i}',
            'serial_number': f'SN{i:06d}',
            'department': ['内科', '外科'][i % 2],
            'location': f'Lab-{i}',
            'status': 'online' if i != 3 else 'offline',
            'last_calibration': (today - timedelta(days=30)).isoformat(),
            'next_calibration': (today + timedelta(days=(i - 3))).isoformat(),
            'supported_tests': 'TP,ALT,GLU',
            'daily_capacity': 100 + i * 10,
        }
        for i in range(1, 11)
    ]


@pytest.fixture
def loaded_patient_repo(patient_repo, sample_patient_records):
    patient_repo.load_from_records(sample_patient_records)
    return patient_repo


@pytest.fixture
def loaded_lab_repo(lab_repo, sample_lab_records):
    lab_repo.load_from_records(sample_lab_records)
    return lab_repo


@pytest.fixture
def loaded_instrument_repo(instrument_repo, sample_instrument_records):
    instrument_repo.load_from_records(sample_instrument_records)
    return instrument_repo
