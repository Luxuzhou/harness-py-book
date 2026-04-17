"""
调度器与调度任务的单元测试。
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.repositories import (
    AnomalyRepository, AuditRepository, InstrumentRepository,
    LabResultRepository, PatientRepository,
)
from app.services.anomaly_rule_engine import (
    AnomalyRuleEngine, load_default_rules,
)
from app.services.scheduler import Scheduler
from app.services.tasks.anomaly_scan import (
    AnomalyScanTask, AnomalyScanConfig,
)
from app.services.tasks.data_refresh import (
    DataRefreshTask, DataRefreshConfig,
)
from app.services.tasks.report_generation import (
    ReportGenerationTask, ReportGenerationConfig,
)


class TestScheduler:
    def test_submit_interval(self):
        sc = Scheduler()
        tid = sc.submit_interval('t1', lambda: 'ok', seconds=60)
        tasks = sc.list_tasks()
        assert any(t['task_id'] == tid for t in tasks)

    def test_submit_daily(self):
        sc = Scheduler()
        tid = sc.submit_daily('daily', lambda: 'ok', '02:30')
        t = sc.get_task(tid)
        assert t['cron_expr'] == 'daily@02:30'
        assert t['next_run'] is not None

    def test_pause_and_resume(self):
        sc = Scheduler()
        tid = sc.submit_interval('t1', lambda: 'ok', seconds=60)
        assert sc.pause(tid) is True
        assert sc.get_task(tid)['enabled'] is False
        assert sc.resume(tid) is True
        assert sc.get_task(tid)['enabled'] is True

    def test_cancel(self):
        sc = Scheduler()
        tid = sc.submit_interval('t1', lambda: 'ok', seconds=60)
        assert sc.cancel(tid) is True
        assert sc.get_task(tid) is None

    def test_execute_updates_counters(self):
        sc = Scheduler(tick_seconds=0.05)
        counter = {'count': 0}

        def fn():
            counter['count'] += 1
            return counter['count']

        tid = sc.submit_interval('inc', fn, seconds=1, start_after_seconds=0)
        sc.start()
        time.sleep(0.3)
        sc.stop()
        task = sc.get_task(tid)
        assert task['run_count'] >= 1
        assert counter['count'] >= 1

    def test_failed_task_logs(self):
        sc = Scheduler(tick_seconds=0.05)

        def boom():
            raise ValueError('boom')

        tid = sc.submit_interval('boom', boom, seconds=10, start_after_seconds=0)
        sc.start()
        time.sleep(0.2)
        sc.stop()
        task = sc.get_task(tid)
        assert task['fail_count'] >= 1
        assert task['last_status'] == 'failed'
        assert 'ValueError' in task['last_error']

    def test_recent_runs_tracks_history(self):
        sc = Scheduler(tick_seconds=0.05)
        sc.submit_interval(
            'h', lambda: 'ok', seconds=10, start_after_seconds=0,
        )
        sc.start()
        time.sleep(0.2)
        sc.stop()
        assert len(sc.recent_runs()) >= 1


class TestAnomalyScanTask:
    def test_run_triggers_anomalies(self):
        ar = AnomalyRepository()
        lr = LabResultRepository()
        ir = InstrumentRepository()
        # 灌入一条会触发异常的 lab_result
        lr.create({
            'result_id': 'R1', 'patient_id': 'P1',
            'step_code': 'TP', 'value': 100, 'unit': 'g/L',
            'visit_date': datetime.now(),
        })
        eng = AnomalyRuleEngine(ar, lab_repo=lr, instrument_repo=ir)
        load_default_rules(eng)
        scan = AnomalyScanTask(
            lab_repo=lr, instrument_repo=ir, rule_engine=eng,
            config=AnomalyScanConfig(dispatch_notifications=False),
        )
        summary = scan.run()
        assert summary['lab_result']['scanned'] >= 1
        assert summary['lab_result']['triggered'] >= 1

    def test_lookback_filter(self):
        ar = AnomalyRepository()
        lr = LabResultRepository()
        ir = InstrumentRepository()
        # 旧数据（lookback 之外）
        old = datetime.now() - timedelta(days=30)
        lr.create({
            'result_id': 'R_old', 'patient_id': 'P1',
            'step_code': 'TP', 'value': 100, 'unit': 'g/L',
            'visit_date': old,
        })
        eng = AnomalyRuleEngine(ar, lab_repo=lr)
        load_default_rules(eng)
        scan = AnomalyScanTask(
            lab_repo=lr, instrument_repo=ir, rule_engine=eng,
            config=AnomalyScanConfig(lookback_hours=1,
                                      dispatch_notifications=False),
        )
        summary = scan.run()
        assert summary['lab_result']['scanned'] == 0


class TestDataRefreshTask:
    def test_refresh_missing_files_skipped(self, tmp_path):
        pr, lr, ir = (PatientRepository(), LabResultRepository(),
                      InstrumentRepository())
        task = DataRefreshTask(
            pr, lr, ir,
            config=DataRefreshConfig(data_dir=tmp_path),
        )
        summary = task.run()
        assert summary['patients'].get('skipped') is True
        assert summary['lab_results'].get('skipped') is True

    def test_refresh_with_csvs(self, tmp_path):
        # 写最小 CSV
        (tmp_path / 'patients.csv').write_text(
            'patient_id,name,id_card,gender,age,department,diagnosis\n'
            'P1,张三,11010119900101001X,male,30,内科,高血压\n',
            encoding='utf-8',
        )
        (tmp_path / 'lab_results.csv').write_text(
            'result_id,patient_id,step_code,step_name,value,unit,'
            'department_id,visit_date,flag\n'
            'R1,P1,TP,总蛋白,70.5,g/L,INS-001,2026-01-01 10:00:00,N\n',
            encoding='utf-8',
        )
        (tmp_path / 'instruments.csv').write_text(
            'department_id,name,manufacturer,model,serial_number,'
            'department,location,status,last_calibration,'
            'next_calibration,supported_tests,daily_capacity\n'
            'INS-001,Analyzer,Roche,M1,SN1,内科,Lab-1,online,'
            '2026-01-01,2026-04-01,"TP,ALT",100\n',
            encoding='utf-8',
        )
        pr, lr, ir = (PatientRepository(), LabResultRepository(),
                      InstrumentRepository())
        task = DataRefreshTask(
            pr, lr, ir,
            config=DataRefreshConfig(data_dir=tmp_path),
        )
        summary = task.run()
        assert summary['patients']['loaded'] >= 1
        assert summary['lab_results']['loaded'] >= 1
        assert summary['instruments']['loaded'] >= 1


class TestReportGenerationTask:
    def test_generate_writes_files(self, tmp_path):
        pr, lr, ir, ar, aur = (
            PatientRepository(), LabResultRepository(),
            InstrumentRepository(), AnomalyRepository(),
            AuditRepository(log_dir=tmp_path / 'audit'),
        )
        pr.create({'patient_id': 'P1', 'name': '张三',
                   'id_card': 'A', 'gender': 'male', 'age': 30,
                   'department': '内科'})
        task = ReportGenerationTask(
            pr, lr, ir, ar, aur,
            config=ReportGenerationConfig(
                output_dir=tmp_path / 'reports',
                period='daily',
                include_raw_json=True,
                include_markdown=True,
            ),
        )
        summary = task.run()
        assert len(summary['files']) == 2
        for f in summary['files']:
            assert Path(f).exists()

    def test_cleanup_old_reports(self, tmp_path):
        import os
        out = tmp_path / 'reports'
        out.mkdir()
        old = out / 'daily-old.json'
        old.write_text('{}', encoding='utf-8')
        os.utime(str(old), (time.time() - 3600 * 24 * 120,
                             time.time() - 3600 * 24 * 120))
        pr, lr, ir, ar = (
            PatientRepository(), LabResultRepository(),
            InstrumentRepository(), AnomalyRepository(),
        )
        task = ReportGenerationTask(
            pr, lr, ir, ar,
            config=ReportGenerationConfig(
                output_dir=out, period='daily', retention_days=90,
            ),
        )
        summary = task.run()
        assert summary['removed_old_reports'] >= 1
