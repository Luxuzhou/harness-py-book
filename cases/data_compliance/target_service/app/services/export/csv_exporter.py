"""
CSV 导出实现。

负责把查询结果转换为 CSV，并保证：
- UTF-8 BOM 头（给 Excel 直接打开不乱码）
- 字段级别的 PII 脱敏过滤
- 最大行数限制（防止导出全库）
- 大文件流式写入
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CsvExportConfig:
    """CSV 导出配置。"""
    include_bom: bool = True
    delimiter: str = ','
    max_rows: int = 100_000
    mask_fields: List[str] = field(default_factory=lambda: [
        'name', 'id_card', 'phone',
    ])
    include_metadata_comment: bool = True


class CsvExporter:
    """
    将结构化记录（dict 列表）导出为 CSV。

    用法：
        exporter = CsvExporter(output_dir=Path('exports'))
        result = exporter.export(records, fields=['patient_id', 'name', ...],
                                 filename='patients_20260101.csv')
    """

    def __init__(
        self,
        output_dir: Path,
        config: Optional[CsvExportConfig] = None,
        mask_fn: Optional[Callable[[str, Any], Any]] = None,
    ):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or CsvExportConfig()
        self.mask_fn = mask_fn or self._default_mask

    def export(
        self,
        records: Iterable[Dict[str, Any]],
        fields: List[str],
        filename: str,
        apply_mask: bool = True,
    ) -> Dict[str, Any]:
        """
        导出到 output_dir/filename。

        apply_mask=True 时，对 config.mask_fields 中的字段运行 mask_fn。
        返回 {path, rows_written, bytes}
        """
        path = self.output_dir / filename
        written = 0
        mode = 'w'
        encoding = 'utf-8-sig' if self.config.include_bom else 'utf-8'

        with open(path, mode, encoding=encoding, newline='') as f:
            if self.config.include_metadata_comment:
                f.write(f'# exported_at={datetime.now().isoformat()}\n')
                f.write(f'# rows_limit={self.config.max_rows}\n')
                if apply_mask:
                    f.write(
                        f'# masked_fields={",".join(self.config.mask_fields)}\n')
            writer = csv.DictWriter(
                f, fieldnames=fields, delimiter=self.config.delimiter,
                extrasaction='ignore',
            )
            writer.writeheader()
            for rec in records:
                if written >= self.config.max_rows:
                    logger.warning(
                        'CsvExporter hit max_rows=%d, truncating',
                        self.config.max_rows,
                    )
                    break
                row = self._prepare_row(rec, fields, apply_mask)
                writer.writerow(row)
                written += 1

        size = path.stat().st_size
        logger.info('csv export %s: rows=%d bytes=%d', path, written, size)
        return {
            'path': str(path),
            'rows_written': written,
            'bytes': size,
            'fields': fields,
            'masked': apply_mask,
        }

    def export_to_string(
        self,
        records: Iterable[Dict[str, Any]],
        fields: List[str],
        apply_mask: bool = True,
    ) -> str:
        """导出为字符串（不落盘），用于 HTTP 直接返回。"""
        buf = io.StringIO()
        writer = csv.DictWriter(
            buf, fieldnames=fields, delimiter=self.config.delimiter,
            extrasaction='ignore',
        )
        writer.writeheader()
        written = 0
        for rec in records:
            if written >= self.config.max_rows:
                break
            writer.writerow(self._prepare_row(rec, fields, apply_mask))
            written += 1
        return buf.getvalue()

    def _prepare_row(
        self,
        rec: Dict[str, Any],
        fields: List[str],
        apply_mask: bool,
    ) -> Dict[str, Any]:
        row: Dict[str, Any] = {}
        for f in fields:
            v = rec.get(f, '')
            if apply_mask and f in self.config.mask_fields:
                v = self.mask_fn(f, v)
            row[f] = v
        return row

    @staticmethod
    def _default_mask(field: str, value: Any) -> Any:
        """默认脱敏：姓氏+*、身份证保留前6后4。"""
        if value is None or value == '':
            return value
        s = str(value)
        if field == 'id_card':
            if len(s) >= 10:
                return s[:6] + '*' * (len(s) - 10) + s[-4:]
            return '*' * len(s)
        if field == 'phone':
            if len(s) >= 7:
                return s[:3] + '*' * (len(s) - 7) + s[-4:]
            return '*' * len(s)
        if field == 'name':
            return s[0] + '*' * (len(s) - 1) if len(s) > 1 else s
        return s
