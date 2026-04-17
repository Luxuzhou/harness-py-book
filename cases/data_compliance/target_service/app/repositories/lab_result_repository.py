"""
检验结果仓储。

承担检验结果（lab_results）的数据访问与聚合查询。
结果字段：result_id, patient_id, step_code, step_name, value,
         unit, department_id (关联 instruments), visit_date, flag
"""

from __future__ import annotations

import logging
import statistics as stats_module
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.base import (
    BaseRepository, NotFoundError, Pagination, SortSpec,
)

logger = logging.getLogger(__name__)


class LabResultRepository(BaseRepository[Dict[str, Any]]):
    """检验结果仓储。"""

    def primary_key(self) -> str:
        return 'result_id'

    def indexed_fields(self) -> List[str]:
        return ['result_id', 'patient_id', 'step_code', 'department_id']

    # --- 点查与列查 ---

    def list_by_patient(
        self,
        patient_id: str,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        return self.list(
            filters={'patient_id': patient_id},
            sort=SortSpec('visit_date', 'desc'),
            pagination=pagination,
        )

    def list_by_step_code(
        self,
        step_code: str,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        return self.list(
            filters={'step_code': step_code},
            sort=SortSpec('visit_date', 'desc'),
            pagination=pagination,
        )

    def list_by_instrument(
        self,
        instrument_id: str,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        return self.list(
            filters={'department_id': instrument_id},
            pagination=pagination,
        )

    def list_by_date_range(
        self,
        step_code: Optional[str],
        start: datetime,
        end: datetime,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        def in_range(d: Any) -> bool:
            if isinstance(d, datetime):
                return start <= d <= end
            if isinstance(d, str):
                try:
                    dt = datetime.fromisoformat(d.replace(' ', 'T').rstrip('Z'))
                    return start <= dt <= end
                except Exception:
                    return False
            return False

        filters: Dict[str, Any] = {'visit_date': in_range}
        if step_code:
            filters['step_code'] = step_code
        return self.list(
            filters=filters,
            sort=SortSpec('visit_date'),
            pagination=pagination,
        )

    def list_abnormal(
        self,
        step_code: Optional[str] = None,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        """返回 flag != 'N'（非正常）的结果。"""
        filters: Dict[str, Any] = {'flag': lambda f: f is not None and f != 'N'}
        if step_code:
            filters['step_code'] = step_code
        return self.list(filters=filters, pagination=pagination)

    # --- 聚合 ---

    def value_statistics(
        self,
        step_code: str,
        instrument_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        对某 step_code 的 value 做统计：均值、标准差、分位数。

        可选按 instrument_id 进一步过滤。
        """
        filters: Dict[str, Any] = {'step_code': step_code}
        if instrument_id:
            filters['department_id'] = instrument_id
        records = self.list(filters=filters)
        values = [r.get('value') for r in records
                  if isinstance(r.get('value'), (int, float))]
        if not values:
            return {
                'step_code': step_code,
                'instrument_id': instrument_id,
                'count': 0,
            }
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            'step_code': step_code,
            'instrument_id': instrument_id,
            'count': n,
            'mean': round(stats_module.mean(values), 3),
            'stdev': round(stats_module.pstdev(values), 3) if n > 1 else 0.0,
            'min': sorted_vals[0],
            'max': sorted_vals[-1],
            'p25': sorted_vals[n // 4] if n >= 4 else sorted_vals[0],
            'p50': sorted_vals[n // 2],
            'p75': sorted_vals[int(n * 0.75)],
            'p95': sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1],
        }

    def daily_volume(
        self,
        step_code: Optional[str] = None,
        days: int = 7,
    ) -> List[Tuple[str, int]]:
        """最近 days 天每日的检验量（按 step_code 可选过滤）。"""
        cutoff = datetime.now() - timedelta(days=days)
        filters: Dict[str, Any] = {}
        if step_code:
            filters['step_code'] = step_code
        records = self.list(filters=filters)
        buckets: Dict[str, int] = {}
        for r in records:
            d = r.get('visit_date')
            dt: Optional[datetime] = None
            if isinstance(d, datetime):
                dt = d
            elif isinstance(d, str):
                try:
                    dt = datetime.fromisoformat(d.replace(' ', 'T').rstrip('Z'))
                except Exception:
                    continue
            if dt and dt >= cutoff:
                key = dt.date().isoformat()
                buckets[key] = buckets.get(key, 0) + 1
        return sorted(buckets.items())

    def top_instruments_by_volume(
        self,
        step_code: Optional[str] = None,
        top_n: int = 10,
    ) -> List[Tuple[str, int]]:
        """按检验量 Top N 列出仪器（可选 step_code 过滤）。"""
        filters: Dict[str, Any] = {}
        if step_code:
            filters['step_code'] = step_code
        records = self.list(filters=filters)
        counts: Dict[str, int] = {}
        for r in records:
            iid = r.get('department_id')
            if iid:
                counts[iid] = counts.get(iid, 0) + 1
        return sorted(counts.items(), key=lambda x: -x[1])[:top_n]

    def outlier_detection(
        self,
        step_code: str,
        sigma: float = 3.0,
        instrument_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        基于 k-sigma 规则返回异常值记录。

        先算均值与标准差，再把 |value - mean| > sigma * stdev 的记录挑出。
        """
        stats = self.value_statistics(step_code, instrument_id)
        if stats.get('count', 0) < 10:
            return []
        mean = stats['mean']
        stdev = stats['stdev']
        if stdev == 0:
            return []
        threshold = sigma * stdev
        filters: Dict[str, Any] = {'step_code': step_code}
        if instrument_id:
            filters['department_id'] = instrument_id
        records = self.list(filters=filters)
        outliers = []
        for r in records:
            v = r.get('value')
            if isinstance(v, (int, float)) and abs(v - mean) > threshold:
                r_copy = dict(r)
                r_copy['_deviation'] = round(v - mean, 3)
                r_copy['_z_score'] = round((v - mean) / stdev, 3)
                outliers.append(r_copy)
        outliers.sort(key=lambda x: -abs(x['_z_score']))
        return outliers

    def monthly_abnormal_rate(
        self,
        step_code: str,
        months: int = 6,
    ) -> List[Dict[str, Any]]:
        """最近 months 个月的异常率（按月粒度聚合）。"""
        records = self.list(filters={'step_code': step_code})
        cutoff = datetime.now() - timedelta(days=months * 31)
        buckets: Dict[str, Dict[str, int]] = {}
        for r in records:
            d = r.get('visit_date')
            dt: Optional[datetime] = None
            if isinstance(d, datetime):
                dt = d
            elif isinstance(d, str):
                try:
                    dt = datetime.fromisoformat(d.replace(' ', 'T').rstrip('Z'))
                except Exception:
                    continue
            if not dt or dt < cutoff:
                continue
            key = dt.strftime('%Y-%m')
            b = buckets.setdefault(key, {'total': 0, 'abnormal': 0})
            b['total'] += 1
            if r.get('flag') and r['flag'] != 'N':
                b['abnormal'] += 1
        out = []
        for k in sorted(buckets):
            total = buckets[k]['total']
            ab = buckets[k]['abnormal']
            rate = round(ab / total, 4) if total else 0.0
            out.append({'month': k, 'total': total, 'abnormal': ab, 'rate': rate})
        return out

    def load_from_records(self, records: List[Dict[str, Any]]) -> int:
        """从 lab_results.csv 结果集批量加载。"""
        count = 0
        for r in records:
            if not r.get('result_id'):
                continue
            try:
                self.create(r)
                count += 1
            except Exception as e:
                logger.debug('skip lab_result %s: %s', r.get('result_id'), e)
        logger.info('loaded %d lab results into repository', count)
        return count
