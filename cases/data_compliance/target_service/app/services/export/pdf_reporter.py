"""
PDF 报表（文本版）。

若环境中 reportlab 可用，则生成真实 PDF；否则降级为纯文本 .txt
（扩展名保留 .pdf 以便下游接口一致，内部在响应中声明 format='txt_fallback'）。

在合规案例中，PDF 报表主要用于把 ReportGenerationTask 的结果
发给审计/监管人员，因此内容更偏向"事件摘要 + 关键指标"。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4  # type: ignore
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # type: ignore
    from reportlab.lib.units import mm  # type: ignore
    from reportlab.platypus import (  # type: ignore
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    )
    from reportlab.lib import colors  # type: ignore
    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False


@dataclass
class PdfReportConfig:
    """PDF 报表配置。"""
    title: str = '临床数据合规日报'
    page_size: str = 'A4'
    margin_mm: int = 15
    include_cover: bool = True
    include_toc: bool = False
    footer_note: str = '本报表自动生成，内容已脱敏，仅供合规审计使用。'


class PdfReporter:
    """
    生成 PDF 报表。

    核心方法：
        generate(report_data, filename)
        report_data 一般由 ReportGenerationTask._build_report() 提供。
    """

    def __init__(
        self,
        output_dir: Path,
        config: Optional[PdfReportConfig] = None,
    ):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or PdfReportConfig()

    def generate(
        self,
        report_data: Dict[str, Any],
        filename: str,
    ) -> Dict[str, Any]:
        path = self.output_dir / filename
        if REPORTLAB_AVAILABLE:
            return self._generate_pdf(report_data, path)
        return self._generate_text_fallback(report_data, path)

    # --- 真实 PDF ---

    def _generate_pdf(
        self,
        report_data: Dict[str, Any],
        path: Path,
    ) -> Dict[str, Any]:
        doc = SimpleDocTemplate(
            str(path), pagesize=A4,
            leftMargin=self.config.margin_mm * mm,
            rightMargin=self.config.margin_mm * mm,
            topMargin=self.config.margin_mm * mm,
            bottomMargin=self.config.margin_mm * mm,
        )
        styles = getSampleStyleSheet()
        story: List[Any] = []

        if self.config.include_cover:
            story.append(Paragraph(self.config.title, styles['Title']))
            story.append(Spacer(1, 6 * mm))
            story.append(Paragraph(
                f'生成时间：{report_data.get("generated_at")}', styles['Normal']))
            story.append(Paragraph(
                f'统计周期：{report_data.get("period")}', styles['Normal']))
            story.append(PageBreak())

        # 各个 section
        story.extend(self._section_patient(report_data, styles))
        story.extend(self._section_lab(report_data, styles))
        story.extend(self._section_anomaly(report_data, styles))
        story.extend(self._section_instrument(report_data, styles))
        story.extend(self._section_audit(report_data, styles))

        # 页脚说明
        footer_style = ParagraphStyle(
            'footer', parent=styles['Italic'], fontSize=8,
            textColor=colors.grey, alignment=1,
        )
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(self.config.footer_note, footer_style))

        doc.build(story)
        size = path.stat().st_size
        logger.info('pdf report generated: %s (%d bytes)', path, size)
        return {
            'path': str(path),
            'format': 'pdf',
            'bytes': size,
        }

    def _section_patient(self, report_data: Dict[str, Any], styles):
        po = report_data.get('patient_overview', {})
        items = [
            ['总患者数', po.get('total', 0)],
            ['平均年龄', po.get('avg_age', '-')],
        ]
        for bucket, cnt in (po.get('age_distribution') or {}).items():
            items.append([f'{bucket} 岁', cnt])
        story = [
            Paragraph('一、患者画像', styles['Heading2']),
            self._make_table(items),
            Spacer(1, 6 * mm),
        ]
        return story

    def _section_lab(self, report_data: Dict[str, Any], styles):
        ls = report_data.get('lab_result_summary', {})
        rows = [['指标', '值']]
        rows.append(['检验结果总数', ls.get('total_results', 0)])
        daily = ls.get('daily_volume_7d', [])
        for d, c in daily:
            rows.append([f'{d} 每日量', c])
        story = [
            Paragraph('二、检验量分布', styles['Heading2']),
            self._make_table(rows, has_header=True),
            Spacer(1, 6 * mm),
        ]
        return story

    def _section_anomaly(self, report_data: Dict[str, Any], styles):
        an = report_data.get('anomaly_summary', {})
        rows = [['指标', '值']]
        rows.append(['异常总数', an.get('total', 0)])
        rows.append(['窗口内新增', an.get('in_window_total', 0)])
        rows.append(['平均修复时长（小时）', an.get('mean_time_to_resolve_hours', '-')])
        for sev, cnt in (an.get('by_severity') or {}).items():
            rows.append([f'严重度={sev}', cnt])
        story = [
            Paragraph('三、异常监控', styles['Heading2']),
            self._make_table(rows, has_header=True),
            Spacer(1, 6 * mm),
        ]
        return story

    def _section_instrument(self, report_data: Dict[str, Any], styles):
        ins = report_data.get('instrument_summary', {})
        rows = [['指标', '值']]
        rows.append(['仪器总数', ins.get('total', 0)])
        rows.append(['在线数', ins.get('online', 0)])
        rows.append(['日总产能', ins.get('total_daily_capacity', 0)])
        rows.append(['14 天内到期', ins.get('due_calibration_in_14d', 0)])
        rows.append(['已过期未校准', ins.get('overdue_calibration', 0)])
        story = [
            Paragraph('四、仪器状态', styles['Heading2']),
            self._make_table(rows, has_header=True),
            Spacer(1, 6 * mm),
        ]
        return story

    def _section_audit(self, report_data: Dict[str, Any], styles):
        au = report_data.get('audit_summary', {})
        if au.get('disabled'):
            return [
                Paragraph('五、审计摘要', styles['Heading2']),
                Paragraph('审计仓储未配置。', styles['Italic']),
            ]
        rows = [['指标', '值']]
        rows.append(['24h 审计记录数', au.get('total_records', 0)])
        for k, v in (au.get('by_event_type') or {}).items():
            rows.append([f'事件类型={k}', v])
        return [
            Paragraph('五、审计摘要', styles['Heading2']),
            self._make_table(rows, has_header=True),
        ]

    @staticmethod
    def _make_table(data, has_header: bool = False):
        if not REPORTLAB_AVAILABLE:
            return None
        tbl = Table(data, hAlign='LEFT')
        style_commands = [
            ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]
        if has_header:
            style_commands.append(
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey))
            style_commands.append(('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'))
        tbl.setStyle(TableStyle(style_commands))
        return tbl

    # --- 文本降级 ---

    def _generate_text_fallback(
        self,
        report_data: Dict[str, Any],
        path: Path,
    ) -> Dict[str, Any]:
        logger.warning('reportlab not installed, writing text fallback: %s', path)
        lines: List[str] = []
        lines.append(self.config.title)
        lines.append('=' * len(self.config.title))
        lines.append(f'生成时间：{report_data.get("generated_at")}')
        lines.append(f'统计周期：{report_data.get("period")}')
        lines.append('')
        lines.append('一、患者画像')
        po = report_data.get('patient_overview', {})
        for k in ('total', 'avg_age'):
            lines.append(f'  {k}: {po.get(k)}')
        lines.append('')
        lines.append('二、检验量分布')
        ls = report_data.get('lab_result_summary', {})
        lines.append(f'  检验结果总数: {ls.get("total_results", 0)}')
        for d, c in (ls.get('daily_volume_7d') or []):
            lines.append(f'  {d}: {c}')
        lines.append('')
        lines.append('三、异常监控')
        an = report_data.get('anomaly_summary', {})
        lines.append(f'  异常总数: {an.get("total", 0)}')
        lines.append(f'  MTTR (小时): {an.get("mean_time_to_resolve_hours", "-")}')
        lines.append('')
        lines.append('四、仪器状态')
        ins = report_data.get('instrument_summary', {})
        for k in ('total', 'online', 'total_daily_capacity',
                  'due_calibration_in_14d', 'overdue_calibration'):
            lines.append(f'  {k}: {ins.get(k)}')
        lines.append('')
        lines.append('=' * 60)
        lines.append(self.config.footer_note)

        path.write_text('\n'.join(lines), encoding='utf-8')
        return {
            'path': str(path),
            'format': 'txt_fallback',
            'bytes': path.stat().st_size,
        }
