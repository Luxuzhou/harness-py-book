"""
导出服务测试。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.export import (
    CsvExporter, ExcelExporter, PdfReporter, ExporterFactory,
)
from app.services.export.csv_exporter import CsvExportConfig
from app.services.export.exporter_factory import (
    ExportPolicy, ExportValidationError,
)


# ========== CsvExporter ==========

class TestCsvExporter:
    def test_export_masks_pii(self, tmp_path):
        exp = CsvExporter(tmp_path, config=CsvExportConfig(
            mask_fields=['name', 'id_card'],
        ))
        records = [{
            'patient_id': 'P1', 'name': '张三',
            'id_card': '11010119900101001X', 'age': 30,
        }]
        out = exp.export(
            records, fields=['patient_id', 'name', 'id_card', 'age'],
            filename='patients.csv', apply_mask=True,
        )
        content = Path(out['path']).read_text(encoding='utf-8-sig')
        assert '张*' in content
        assert '110101' in content  # 保留前 6
        assert '001X' in content    # 保留后 4
        assert '19900101' not in content  # 中间脱敏

    def test_export_without_mask(self, tmp_path):
        exp = CsvExporter(tmp_path)
        records = [{'name': '张三', 'id_card': '110101199001010001'}]
        out = exp.export(
            records, fields=['name', 'id_card'],
            filename='patients.csv', apply_mask=False,
        )
        content = Path(out['path']).read_text(encoding='utf-8-sig')
        assert '张三' in content
        assert '110101199001010001' in content

    def test_max_rows_truncates(self, tmp_path):
        exp = CsvExporter(tmp_path, config=CsvExportConfig(max_rows=5))
        records = [{'patient_id': f'P{i}'} for i in range(20)]
        out = exp.export(records, fields=['patient_id'], filename='big.csv')
        assert out['rows_written'] == 5

    def test_export_to_string(self, tmp_path):
        exp = CsvExporter(tmp_path)
        s = exp.export_to_string(
            [{'a': 1, 'b': 2}], fields=['a', 'b'], apply_mask=False,
        )
        assert 'a,b' in s
        assert '1,2' in s


# ========== ExcelExporter ==========

class TestExcelExporter:
    def test_export_fallback_when_no_openpyxl(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'app.services.export.excel_exporter.OPENPYXL_AVAILABLE', False,
        )
        exp = ExcelExporter(tmp_path)
        records = [{'a': 1, 'b': 2}]
        out = exp.export_single(records, fields=['a', 'b'], filename='x.xlsx')
        assert out['format'] == 'csv_fallback'

    def test_export_multi_sheet(self, tmp_path):
        exp = ExcelExporter(tmp_path)
        sheets = {
            'patients': {'fields': ['patient_id'], 'records': [{'patient_id': 'P1'}]},
            'lab': {'fields': ['result_id'], 'records': [{'result_id': 'R1'}]},
        }
        out = exp.export(sheets, 'multi.xlsx')
        assert out['sheet_count'] == 2
        assert out['total_rows'] == 2


# ========== PdfReporter ==========

class TestPdfReporter:
    def test_generate_fallback_when_no_reportlab(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            'app.services.export.pdf_reporter.REPORTLAB_AVAILABLE', False,
        )
        reporter = PdfReporter(tmp_path)
        report = {
            'generated_at': '2026-04-17',
            'period': 'daily',
            'patient_overview': {'total': 10},
            'lab_result_summary': {'total_results': 100,
                                    'daily_volume_7d': []},
            'anomaly_summary': {'total': 5},
            'instrument_summary': {'total': 3, 'online': 2,
                                    'total_daily_capacity': 300,
                                    'due_calibration_in_14d': 0,
                                    'overdue_calibration': 0},
            'audit_summary': {'disabled': True},
        }
        out = reporter.generate(report, 'daily.pdf')
        assert out['format'] == 'txt_fallback'
        content = Path(out['path']).read_text(encoding='utf-8')
        assert '患者画像' in content
        assert '仪器状态' in content


# ========== ExporterFactory ==========

class TestExporterFactory:
    def test_csv_uses_policy_mask_fields(self, tmp_path):
        factory = ExporterFactory(
            default_output_dir=tmp_path,
            policy=ExportPolicy(
                allowed_output_dirs=[tmp_path],
                mandatory_mask_fields=['name', 'phone'],
            ),
        )
        csv = factory.csv()
        assert 'name' in csv.config.mask_fields
        assert 'phone' in csv.config.mask_fields

    def test_validate_request_rejects_unsupported_format(self, tmp_path):
        factory = ExporterFactory(default_output_dir=tmp_path)
        with pytest.raises(ExportValidationError):
            factory.validate_request('docx', fields=[], requested_max_rows=None)

    def test_validate_request_caps_max_rows(self, tmp_path):
        policy = ExportPolicy(max_rows_hard_cap=1000)
        factory = ExporterFactory(default_output_dir=tmp_path, policy=policy)
        with pytest.raises(ExportValidationError):
            factory.validate_request('csv', fields=[], requested_max_rows=10000)

    def test_whitelist_enforced(self, tmp_path):
        factory = ExporterFactory(default_output_dir=tmp_path)
        outside = tmp_path.parent / 'somewhere_else'
        with pytest.raises(ExportValidationError):
            factory.csv(output_dir=outside)

    def test_build_filename_sanitizes(self, tmp_path):
        factory = ExporterFactory(default_output_dir=tmp_path)
        fn = factory.build_filename('patients ../../etc/passwd', 'csv')
        assert '..' not in fn
        assert '/' not in fn
        assert fn.endswith('.csv')

    def test_resolve_max_rows_fallback(self, tmp_path):
        factory = ExporterFactory(
            default_output_dir=tmp_path,
            policy=ExportPolicy(max_rows_soft_cap=500),
        )
        exp = factory.csv(max_rows=None)
        assert exp.config.max_rows == 500
