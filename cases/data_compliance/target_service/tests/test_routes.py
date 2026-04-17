"""
API 路由集成测试（使用 FastAPI TestClient）。

测试每个域路由的基本 CRUD 与关键端点。
注：路由模块内持有全局单例 Repository，每个测试前需手动重置。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import register_routes


@pytest.fixture
def app():
    application = FastAPI()
    from fastapi import APIRouter
    root_router = APIRouter()
    register_routes(root_router)
    application.include_router(root_router, prefix='/api/v1')
    return application


@pytest.fixture
def client(app):
    # 重置所有路由内的单例 Repository
    from app.api.routes.patients import _reset_repo_for_tests as reset_p
    from app.api.routes.lab_results import _reset_repo_for_tests as reset_l
    from app.api.routes.instruments import _reset_repo_for_tests as reset_i
    from app.api.routes.anomalies import _reset_repo_for_tests as reset_a
    from app.api.routes.pathways import _reset_repo_for_tests as reset_pw
    from app.api.routes.exports import _reset_repo_for_tests as reset_e
    from app.api.routes.admin import _reset_repo_for_tests as reset_ad
    for fn in (reset_p, reset_l, reset_i, reset_a, reset_pw, reset_e, reset_ad):
        fn()
    return TestClient(app)


class TestPatientsRoute:
    def test_create_and_get(self, client):
        r = client.post('/api/v1/patients', json={
            'patient_id': 'P1', 'name': '张三',
            'id_card': '11010119900101001X',
            'gender': 'male', 'age': 30,
        })
        assert r.status_code == 200
        # get 应返回脱敏后内容
        g = client.get('/api/v1/patients/P1')
        assert g.status_code == 200
        body = g.json()
        assert body['name'] == '张*'
        assert '110101' in body['id_card']
        assert '001X' in body['id_card']

    def test_list_with_pagination(self, client):
        for i in range(15):
            client.post('/api/v1/patients', json={
                'patient_id': f'P{i:03d}', 'name': f'测试{i}',
                'id_card': f'110101199001011{i:03d}',
                'gender': 'male', 'age': 20 + i,
            })
        r = client.get('/api/v1/patients?page=1&page_size=5')
        body = r.json()
        assert body['total'] == 15
        assert len(body['data']) == 5

    def test_statistics(self, client):
        client.post('/api/v1/patients', json={
            'patient_id': 'P1', 'name': '张三',
            'id_card': 'A', 'gender': 'male', 'age': 30,
        })
        r = client.get('/api/v1/patients/statistics/summary')
        assert r.status_code == 200
        assert r.json()['total'] == 1

    def test_get_not_found(self, client):
        r = client.get('/api/v1/patients/NOPE')
        assert r.status_code == 404

    def test_patch(self, client):
        client.post('/api/v1/patients', json={
            'patient_id': 'P1', 'name': '张三', 'id_card': 'A',
            'gender': 'male', 'age': 30,
        })
        r = client.patch('/api/v1/patients/P1', json={'age': 40})
        assert r.status_code == 200

    def test_delete(self, client):
        client.post('/api/v1/patients', json={
            'patient_id': 'P1', 'name': '张三', 'id_card': 'A',
            'gender': 'male', 'age': 30,
        })
        r = client.delete('/api/v1/patients/P1')
        assert r.status_code == 200
        g = client.get('/api/v1/patients/P1')
        assert g.status_code == 404


class TestLabResultsRoute:
    def test_create_and_list(self, client):
        client.post('/api/v1/lab_results', json={
            'result_id': 'R1', 'patient_id': 'P1',
            'step_code': 'TP', 'value': 70.5,
        })
        r = client.get('/api/v1/lab_results')
        body = r.json()
        assert body['total'] >= 1

    def test_list_by_patient(self, client):
        for i in range(3):
            client.post('/api/v1/lab_results', json={
                'result_id': f'R{i}', 'patient_id': 'P1',
                'step_code': 'TP', 'value': 70.0 + i,
            })
        r = client.get('/api/v1/lab_results?patient_id=P1')
        body = r.json()
        assert body['total'] == 3

    def test_value_stats(self, client):
        for i in range(5):
            client.post('/api/v1/lab_results', json={
                'result_id': f'R{i}', 'patient_id': 'P1',
                'step_code': 'TP', 'value': 60.0 + i * 2,
            })
        r = client.get('/api/v1/lab_results/stats/values?step_code=TP')
        assert r.status_code == 200
        body = r.json()
        assert body['count'] == 5
        assert body['mean'] > 0


class TestInstrumentsRoute:
    def test_create_and_offline_online(self, client):
        client.post('/api/v1/instruments', json={
            'department_id': 'INS-001', 'name': 'Analyzer-1',
            'status': 'online',
        })
        r = client.post('/api/v1/instruments/INS-001/offline',
                        json={'reason': 'maintenance'})
        assert r.status_code == 200
        g = client.get('/api/v1/instruments/INS-001')
        assert g.json()['status'] == 'offline'
        client.post('/api/v1/instruments/INS-001/online')
        g = client.get('/api/v1/instruments/INS-001')
        assert g.json()['status'] == 'online'

    def test_due_calibration(self, client):
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        client.post('/api/v1/instruments', json={
            'department_id': 'INS-DUE', 'name': 'Due',
            'next_calibration': tomorrow,
        })
        r = client.get('/api/v1/instruments/alerts/due?days_ahead=7')
        assert r.status_code == 200
        body = r.json()
        assert body['count'] >= 1


class TestAnomaliesRoute:
    def test_evaluate_triggers_anomalies(self, client):
        r = client.post('/api/v1/anomalies/evaluate_batch', json={
            'records': [{
                'result_id': 'R1', 'patient_id': 'P1',
                'step_code': 'TP', 'value': 99, 'unit': 'g/L',
            }],
            'target_type': 'lab_result',
        })
        assert r.status_code == 200
        body = r.json()
        assert body['scanned'] == 1
        assert body['triggered'] >= 1

    def test_lifecycle(self, client):
        client.post('/api/v1/anomalies/evaluate_batch', json={
            'records': [{
                'result_id': 'R1', 'step_code': 'TP', 'value': 99,
            }],
            'target_type': 'lab_result',
        })
        open_list = client.get('/api/v1/anomalies').json()
        assert open_list['total'] >= 1
        aid = open_list['data'][0]['anomaly_id']
        client.post(f'/api/v1/anomalies/{aid}/ack',
                     json={'handler': 'alice'})
        res = client.post(f'/api/v1/anomalies/{aid}/resolve',
                            json={'handler': 'alice', 'resolution_note': 'ok'})
        assert res.status_code == 200

    def test_rules_list_has_defaults(self, client):
        r = client.get('/api/v1/anomalies/rules/list')
        body = r.json()
        assert body['count'] >= 5


class TestPathwaysRoute:
    def test_submit_and_poll(self, client):
        import time
        r = client.post('/api/v1/pathways/tasks', json={
            'task_name': 't1', 'step_code': 'TP',
            'start_immediately': True,
        })
        assert r.status_code == 200
        body = r.json()
        tid = body['task_id']
        # 等待后台线程完成
        for _ in range(100):
            time.sleep(0.02)
            detail = client.get(f'/api/v1/pathways/tasks/{tid}').json()
            if detail['status'] in {'SUCCEEDED', 'FAILED'}:
                break
        assert detail['status'] == 'SUCCEEDED'
        result = client.get(f'/api/v1/pathways/results/{tid}').json()
        assert 'compliance_rate' in result['result']


class TestExportsRoute:
    def test_export_patients_csv(self, client, tmp_path):
        client.post('/api/v1/patients', json={
            'patient_id': 'P1', 'name': '张三',
            'id_card': '11010119900101001X',
            'gender': 'male', 'age': 30,
        })
        r = client.post('/api/v1/exports/patients', json={
            'format': 'csv',
            'fields': ['patient_id', 'name', 'id_card', 'age'],
            'apply_mask': True,
        })
        assert r.status_code == 200
        body = r.json()
        assert body['rows_written'] == 1
        assert body['masked'] is True

    def test_export_unknown_format_400(self, client):
        r = client.post('/api/v1/exports/patients', json={
            'format': 'docx',
        })
        assert r.status_code == 400


class TestAdminRoute:
    def test_health_returns_counts(self, client):
        r = client.get('/api/v1/admin/health')
        assert r.status_code == 200
        body = r.json()
        assert 'patients_loaded' in body
        assert 'rules_loaded' in body

    def test_trigger_scan(self, client):
        client.post('/api/v1/lab_results', json={
            'result_id': 'R1', 'patient_id': 'P1',
            'step_code': 'TP', 'value': 99,
        })
        r = client.post('/api/v1/admin/scan/anomalies?lookback_hours=48')
        assert r.status_code == 200
