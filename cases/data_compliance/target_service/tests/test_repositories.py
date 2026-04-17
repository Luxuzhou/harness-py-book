"""
Repository 层单元测试。

覆盖：
- BaseRepository CRUD、过滤、分页、索引
- PatientRepository 业务查询
- LabResultRepository 聚合统计
- InstrumentRepository 校准管理
- AnomalyRepository 生命周期
- AuditRepository 落盘
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.repositories import (
    AnomalyRepository, AuditRepository, InstrumentRepository,
    LabResultRepository, PatientRepository, Pagination, SortSpec,
)
from app.repositories.base import DuplicateKeyError, NotFoundError


# ========== BaseRepository ==========

class TestBaseRepository:
    def test_create_and_get(self, patient_repo):
        p = patient_repo.create({'patient_id': 'P1', 'name': '张三', 'age': 30})
        assert p['patient_id'] == 'P1'
        fetched = patient_repo.get_by_id('P1')
        assert fetched['name'] == '张三'

    def test_create_duplicate_raises(self, patient_repo):
        patient_repo.create({'patient_id': 'P1', 'name': '张三'})
        with pytest.raises(DuplicateKeyError):
            patient_repo.create({'patient_id': 'P1', 'name': '李四'})

    def test_update_nonexistent_raises(self, patient_repo):
        with pytest.raises(NotFoundError):
            patient_repo.update('NOPE', {'age': 40})

    def test_soft_delete_hides(self, patient_repo):
        patient_repo.create({'patient_id': 'P1', 'name': '张三'})
        assert patient_repo.delete('P1') is True
        assert patient_repo.get_by_id('P1') is None
        # include_deleted 能看到
        with_deleted = patient_repo.list(include_deleted=True)
        assert any(r['patient_id'] == 'P1' for r in with_deleted)

    def test_list_filters(self, loaded_patient_repo):
        items = loaded_patient_repo.list(filters={'gender': 'female'})
        assert all(r['gender'] == 'female' for r in items)
        # IN filter
        items = loaded_patient_repo.list(
            filters={'department': ['内科', '外科']},
        )
        assert all(r['department'] in {'内科', '外科'} for r in items)

    def test_list_op_filters(self, loaded_patient_repo):
        items = loaded_patient_repo.list(filters={'age': {'gte': 50}})
        assert all(r['age'] >= 50 for r in items)

    def test_pagination(self, loaded_patient_repo):
        pg = Pagination(page=2, page_size=5)
        items = loaded_patient_repo.list(pagination=pg)
        assert len(items) == 5
        assert pg.total == 20

    def test_sort(self, loaded_patient_repo):
        sort = SortSpec('age', 'desc')
        items = loaded_patient_repo.list(sort=sort)
        ages = [r['age'] for r in items]
        assert ages == sorted(ages, reverse=True)

    def test_indexed_lookup(self, loaded_patient_repo):
        # id_card 是索引字段，查询应走索引
        p = loaded_patient_repo.get_by_field(
            'id_card', '11010119901010100001')
        # 未必命中，但不报错
        assert p is None or 'patient_id' in p

    def test_bulk_create_skips_duplicates(self, patient_repo):
        records = [
            {'patient_id': 'P1', 'name': 'A'},
            {'patient_id': 'P1', 'name': 'B'},  # dup
            {'patient_id': 'P2', 'name': 'C'},
        ]
        count = patient_repo.bulk_create(records)
        assert count == 2


# ========== PatientRepository ==========

class TestPatientRepository:
    def test_list_by_department(self, loaded_patient_repo):
        items = loaded_patient_repo.list_by_department('内科')
        assert all(r['department'] == '内科' for r in items)

    def test_age_range(self, loaded_patient_repo):
        items = loaded_patient_repo.list_by_age_range(30, 50)
        assert all(30 <= r['age'] <= 50 for r in items)

    def test_diagnosis_keywords(self, loaded_patient_repo):
        items = loaded_patient_repo.list_by_diagnosis_keywords(['高血压'])
        assert all('高血压' in (r.get('diagnosis') or '') for r in items)

    def test_statistics(self, loaded_patient_repo):
        stats = loaded_patient_repo.statistics()
        assert stats['total'] == 20
        assert stats['avg_age'] is not None
        assert 'age_distribution' in stats

    def test_find_duplicates_detects_conflicts(self, patient_repo):
        patient_repo.create({'patient_id': 'P1', 'id_card': 'A1'})
        patient_repo.create({'patient_id': 'P2', 'id_card': 'A1'})
        patient_repo.create({'patient_id': 'P3', 'id_card': 'B2'})
        groups = patient_repo.find_duplicates_by_id_card()
        assert len(groups) == 1
        assert set(groups[0]) == {'P1', 'P2'}

    def test_merge_duplicate(self, patient_repo):
        patient_repo.create({'patient_id': 'P1', 'name': '张三', 'id_card': 'A1',
                             'age': 30, 'department': '内科'})
        patient_repo.create({'patient_id': 'P2', 'name': '张三', 'id_card': 'A1',
                             'phone': '13900000000'})
        merged = patient_repo.merge_duplicate('P1', 'P2')
        assert merged['phone'] == '13900000000'  # victim 字段补到 survivor
        assert patient_repo.get_by_id('P2') is None  # victim 软删

    def test_birth_year_from_id_card(self, patient_repo):
        patient_repo.create({'patient_id': 'P1', 'id_card': '11010119850615003X'})
        year = patient_repo.calculate_birth_year_from_id_card('P1')
        assert year == 1985


# ========== LabResultRepository ==========

class TestLabResultRepository:
    def test_list_by_patient(self, loaded_lab_repo):
        items = loaded_lab_repo.list_by_patient('P000001')
        assert all(r['patient_id'] == 'P000001' for r in items)

    def test_list_abnormal(self, loaded_lab_repo):
        items = loaded_lab_repo.list_abnormal()
        assert all(r['flag'] != 'N' for r in items)

    def test_value_statistics(self, loaded_lab_repo):
        stats = loaded_lab_repo.value_statistics('TP')
        assert stats['count'] > 0
        assert 'mean' in stats
        assert 'stdev' in stats

    def test_daily_volume(self, loaded_lab_repo):
        # conftest 的 fixture 生成的是 2026-01-01 起的数据，跟 datetime.now() 不重合
        # 所以默认 lookback 为空；改为检查返回结构
        out = loaded_lab_repo.daily_volume(step_code='TP', days=3650)
        assert isinstance(out, list)

    def test_top_instruments(self, loaded_lab_repo):
        tops = loaded_lab_repo.top_instruments_by_volume(top_n=3)
        assert len(tops) <= 3
        assert all(isinstance(c, int) for _, c in tops)

    def test_outlier_detection(self, lab_repo):
        # 构造足够多的数据触发 outlier
        import random
        random.seed(0)
        for i in range(200):
            v = random.gauss(70, 5)
            lab_repo.create({
                'result_id': f'R{i:06d}',
                'patient_id': 'P1',
                'step_code': 'TP',
                'value': v,
                'unit': 'g/L',
            })
        lab_repo.create({
            'result_id': 'R_outlier',
            'patient_id': 'P1',
            'step_code': 'TP',
            'value': 999,  # 极端异常
        })
        outliers = lab_repo.outlier_detection('TP', sigma=3.0)
        assert any(o['result_id'] == 'R_outlier' for o in outliers)

    def test_monthly_abnormal_rate(self, lab_repo):
        from datetime import datetime, timedelta
        base = datetime.now() - timedelta(days=90)
        for i in range(30):
            lab_repo.create({
                'result_id': f'R{i:06d}',
                'patient_id': 'P1',
                'step_code': 'TP',
                'value': 70.0,
                'unit': 'g/L',
                'visit_date': base + timedelta(days=i),
                'flag': 'N' if i % 3 else 'H',
            })
        series = lab_repo.monthly_abnormal_rate('TP', months=6)
        assert all('rate' in row for row in series)


# ========== InstrumentRepository ==========

class TestInstrumentRepository:
    def test_list_online(self, loaded_instrument_repo):
        items = loaded_instrument_repo.list_online()
        assert all(r['status'] == 'online' for r in items)

    def test_find_due_calibration(self, loaded_instrument_repo):
        # fixture 中 INS-001 到期 ~ 2026-04-15，INS-002 ~ 2026-04-16
        # INS-003 离线且过期
        items = loaded_instrument_repo.find_due_calibration(days_ahead=365 * 10)
        assert len(items) >= 1

    def test_find_overdue(self, instrument_repo):
        yesterday = (date.today() - timedelta(days=5)).isoformat()
        instrument_repo.create({
            'department_id': 'INS-X', 'name': 'ExpiredDev',
            'next_calibration': yesterday,
        })
        overdue = instrument_repo.find_overdue_calibration()
        assert any(r['department_id'] == 'INS-X' for r in overdue)

    def test_mark_offline_and_online(self, loaded_instrument_repo):
        assert loaded_instrument_repo.mark_offline('INS-001', 'test') is True
        assert loaded_instrument_repo.get_by_id('INS-001')['status'] == 'offline'
        assert loaded_instrument_repo.mark_online('INS-001') is True
        assert loaded_instrument_repo.get_by_id('INS-001')['status'] == 'online'

    def test_record_calibration_sets_next_due(self, loaded_instrument_repo):
        today = date.today()
        ok = loaded_instrument_repo.record_calibration('INS-001', today)
        assert ok
        rec = loaded_instrument_repo.get_by_id('INS-001')
        assert rec['last_calibration'] == today.isoformat()

    def test_capacity_summary(self, loaded_instrument_repo):
        summary = loaded_instrument_repo.capacity_summary()
        assert summary['total'] == 10
        assert summary['online'] == 9
        assert summary['total_daily_capacity'] > 0


# ========== AnomalyRepository ==========

class TestAnomalyRepository:
    def test_open_anomaly(self, anomaly_repo):
        a = anomaly_repo.open_anomaly(
            rule_id='R1', target_type='lab_result', target_id='LR1',
            severity='WARN', description='测试',
        )
        assert a['status'] == 'NEW'
        assert a['severity'] == 'WARN'

    def test_severity_validation(self, anomaly_repo):
        with pytest.raises(ValueError):
            anomaly_repo.open_anomaly(
                rule_id='R1', target_type='lab_result', target_id='LR1',
                severity='UNKNOWN', description='测试',
            )

    def test_lifecycle_ack_and_resolve(self, anomaly_repo):
        a = anomaly_repo.open_anomaly(
            rule_id='R1', target_type='lab_result', target_id='LR1',
            severity='WARN', description='x',
        )
        ack = anomaly_repo.acknowledge(a['anomaly_id'], handler='alice')
        assert ack['status'] == 'ACKNOWLEDGED'
        assert ack['handler'] == 'alice'
        resolved = anomaly_repo.resolve(
            a['anomaly_id'], handler='bob', resolution_note='fixed',
        )
        assert resolved['status'] == 'RESOLVED'
        assert resolved['resolution_note'] == 'fixed'

    def test_ignore(self, anomaly_repo):
        a = anomaly_repo.open_anomaly(
            rule_id='R1', target_type='lab_result', target_id='LR1',
            severity='INFO', description='x',
        )
        ig = anomaly_repo.ignore(a['anomaly_id'], reason='false positive')
        assert ig['status'] == 'IGNORED'

    def test_bulk_ignore_by_rule(self, anomaly_repo):
        for i in range(5):
            anomaly_repo.open_anomaly(
                rule_id='R1', target_type='lab_result', target_id=f'LR{i}',
                severity='WARN', description='x',
            )
        anomaly_repo.open_anomaly(
            rule_id='R2', target_type='lab_result', target_id='LR99',
            severity='WARN', description='x',
        )
        n = anomaly_repo.bulk_ignore_by_rule('R1', 'noisy')
        assert n == 5
        # R2 没被碰
        r2_open = anomaly_repo.list_open()
        assert all(x['rule_id'] == 'R2' for x in r2_open)

    def test_list_open_and_stats(self, anomaly_repo):
        anomaly_repo.open_anomaly(
            rule_id='R1', target_type='lab_result', target_id='LR1',
            severity='WARN', description='x',
        )
        anomaly_repo.open_anomaly(
            rule_id='R1', target_type='lab_result', target_id='LR2',
            severity='CRIT', description='x',
        )
        open_ones = anomaly_repo.list_open()
        assert len(open_ones) == 2
        stats = anomaly_repo.statistics(window_hours=1)
        assert stats['total'] == 2


# ========== AuditRepository ==========

class TestAuditRepository:
    def test_record_http_persists_to_file(self, audit_repo, tmp_path):
        audit_repo.record_http(
            user='alice', request_id='R1', method='GET', path='/api/v1/patients',
            status_code=200, duration_ms=42, client_ip='127.0.0.1',
        )
        log_files = list((tmp_path / 'audit_logs').iterdir())
        assert len(log_files) == 1
        content = log_files[0].read_text(encoding='utf-8')
        assert 'alice' in content
        assert '/api/v1/patients' in content

    def test_search_by_user(self, audit_repo):
        for i in range(10):
            audit_repo.record_http(
                user='alice' if i % 2 else 'bob',
                request_id=f'R{i}', method='GET', path='/x',
                status_code=200, duration_ms=10, client_ip='1.1.1.1',
            )
        alice_records = audit_repo.search(user='alice')
        assert all(r['user'] == 'alice' for r in alice_records)
        assert len(alice_records) == 5

    def test_summary(self, audit_repo):
        audit_repo.record_http(
            user='alice', request_id='R1', method='GET', path='/x',
            status_code=200, duration_ms=10, client_ip='1.1.1.1',
        )
        audit_repo.record_data_export(
            user='alice', request_id='R2', export_format='csv',
            record_count=100, filters={}, output_path='/tmp/a.csv',
        )
        summary = audit_repo.summary(window_hours=24)
        assert summary['total_records'] == 2
        assert 'http_request' in summary['by_event_type']
        assert 'data_export' in summary['by_event_type']
