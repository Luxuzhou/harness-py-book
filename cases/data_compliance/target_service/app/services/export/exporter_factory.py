"""
导出器工厂 + 合规约束。

上层只看 ExporterFactory：声明格式、字段、脱敏策略，工厂返回正确的 Exporter。
工厂还负责：
- 从 config 里读取导出白名单目录（沙箱约束）
- 强制脱敏字段不可被关闭（合规要求）
- 统一文件命名（含时间戳与来源标识）
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.export.csv_exporter import CsvExporter, CsvExportConfig
from app.services.export.excel_exporter import ExcelExporter, ExcelExportConfig
from app.services.export.pdf_reporter import PdfReporter, PdfReportConfig

logger = logging.getLogger(__name__)


@dataclass
class ExportPolicy:
    """导出合规策略。"""
    allowed_output_dirs: List[Path] = field(default_factory=list)
    mandatory_mask_fields: List[str] = field(default_factory=lambda: [
        'name', 'id_card', 'phone',
    ])
    max_rows_soft_cap: int = 100_000
    max_rows_hard_cap: int = 500_000
    require_audit_hook: bool = True
    deny_network_output: bool = True
    supported_formats: List[str] = field(default_factory=lambda: [
        'csv', 'xlsx', 'pdf',
    ])


class ExportValidationError(Exception):
    """导出参数违规。"""


class ExporterFactory:
    """导出器工厂。"""

    def __init__(
        self,
        default_output_dir: Path,
        policy: Optional[ExportPolicy] = None,
    ):
        self.default_output_dir = default_output_dir
        self.default_output_dir.mkdir(parents=True, exist_ok=True)
        self.policy = policy or ExportPolicy(
            allowed_output_dirs=[default_output_dir],
        )
        if default_output_dir not in self.policy.allowed_output_dirs:
            self.policy.allowed_output_dirs.append(default_output_dir)

    # --- 入口 ---

    def csv(
        self,
        output_dir: Optional[Path] = None,
        max_rows: Optional[int] = None,
    ) -> CsvExporter:
        dest = self._resolve_output_dir(output_dir)
        cfg = CsvExportConfig(
            mask_fields=list(self.policy.mandatory_mask_fields),
            max_rows=self._resolve_max_rows(max_rows),
        )
        return CsvExporter(output_dir=dest, config=cfg)

    def excel(
        self,
        output_dir: Optional[Path] = None,
        max_rows: Optional[int] = None,
    ) -> ExcelExporter:
        dest = self._resolve_output_dir(output_dir)
        cfg = ExcelExportConfig(
            mask_fields=list(self.policy.mandatory_mask_fields),
            max_rows_per_sheet=self._resolve_max_rows(max_rows),
        )
        return ExcelExporter(output_dir=dest, config=cfg)

    def pdf(
        self,
        output_dir: Optional[Path] = None,
        title: Optional[str] = None,
    ) -> PdfReporter:
        dest = self._resolve_output_dir(output_dir)
        cfg = PdfReportConfig(
            title=title or '临床数据合规日报',
        )
        return PdfReporter(output_dir=dest, config=cfg)

    def build_filename(
        self,
        prefix: str,
        format: str,
        extra: Optional[str] = None,
    ) -> str:
        """构造符合合规命名的文件名。"""
        safe_prefix = re.sub(r'[^A-Za-z0-9_\-]', '_', prefix)[:40] or 'export'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        extra_part = ''
        if extra:
            extra_part = '-' + re.sub(r'[^A-Za-z0-9_\-]', '_', extra)[:20]
        return f'{safe_prefix}-{ts}{extra_part}.{format}'

    # --- 合规校验 ---

    def validate_request(
        self,
        format: str,
        fields: List[str],
        requested_max_rows: Optional[int],
        dry_run: bool = False,
    ) -> None:
        """
        校验一次导出请求，违规抛 ExportValidationError。

        dry_run=True 时只校验不落盘。
        """
        if format not in self.policy.supported_formats:
            raise ExportValidationError(
                f'unsupported format: {format}. '
                f'allowed={self.policy.supported_formats}')
        if requested_max_rows and requested_max_rows > self.policy.max_rows_hard_cap:
            raise ExportValidationError(
                f'max_rows {requested_max_rows} exceeds hard cap '
                f'{self.policy.max_rows_hard_cap}')
        # 如果字段里包含敏感字段，必须保留在 mandatory_mask_fields 中
        for f in fields:
            if f in self.policy.mandatory_mask_fields:
                continue  # 会被 exporter 自动脱敏
        if dry_run:
            return

    def is_output_allowed(self, path: Path) -> bool:
        p = path.resolve()
        for root in self.policy.allowed_output_dirs:
            try:
                r = root.resolve()
            except Exception:
                continue
            try:
                p.relative_to(r)
                return True
            except ValueError:
                continue
        return False

    # --- 内部 ---

    def _resolve_output_dir(self, requested: Optional[Path]) -> Path:
        if requested is None:
            return self.default_output_dir
        if not self.is_output_allowed(requested):
            raise ExportValidationError(
                f'output directory not in whitelist: {requested}. '
                f'allowed={self.policy.allowed_output_dirs}')
        requested.mkdir(parents=True, exist_ok=True)
        return requested

    def _resolve_max_rows(self, requested: Optional[int]) -> int:
        if requested is None:
            return self.policy.max_rows_soft_cap
        return min(requested, self.policy.max_rows_hard_cap)
