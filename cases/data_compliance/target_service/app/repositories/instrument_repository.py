"""
仪器设备仓储。

承担实验室/诊疗设备的元数据访问。设备字段包括：
- department_id（主键，INS-前缀）
- name / manufacturer / model / serial_number
- department (设备所属科室)
- location / status / last_calibration / next_calibration
- supported_tests / daily_capacity
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.repositories.base import BaseRepository, Pagination, SortSpec

logger = logging.getLogger(__name__)


class InstrumentRepository(BaseRepository[Dict[str, Any]]):
    """仪器设备仓储。"""

    def primary_key(self) -> str:
        return 'department_id'

    def indexed_fields(self) -> List[str]:
        return ['department_id', 'serial_number', 'department', 'status']

    def list_online(self, department: Optional[str] = None) -> List[Dict[str, Any]]:
        """返回处于 online 状态的设备。"""
        filters: Dict[str, Any] = {'status': 'online'}
        if department:
            filters['department'] = department
        return self.list(filters=filters, sort=SortSpec('department_id'))

    def list_by_status(self, status: str) -> List[Dict[str, Any]]:
        return self.list(filters={'status': status})

    def list_by_manufacturer(self, manufacturer: str) -> List[Dict[str, Any]]:
        return self.list(filters={'manufacturer': manufacturer})

    def list_supporting_test(self, test_code: str) -> List[Dict[str, Any]]:
        """返回支持某检验项目的设备。"""
        def supports(value: Any) -> bool:
            if not value:
                return False
            if isinstance(value, str):
                return test_code in value.split(',')
            if isinstance(value, (list, tuple, set)):
                return test_code in value
            return False
        return self.list(filters={'supported_tests': supports})

    def find_due_calibration(
        self,
        days_ahead: int = 7,
    ) -> List[Dict[str, Any]]:
        """返回未来 days_ahead 天内到期的设备。"""
        today = datetime.now().date()
        deadline = today + timedelta(days=days_ahead)

        def due(next_cal: Any) -> bool:
            if not next_cal:
                return False
            d: Optional[date] = None
            if isinstance(next_cal, date) and not isinstance(next_cal, datetime):
                d = next_cal
            elif isinstance(next_cal, datetime):
                d = next_cal.date()
            elif isinstance(next_cal, str):
                try:
                    d = datetime.strptime(next_cal[:10], '%Y-%m-%d').date()
                except Exception:
                    return False
            return d is not None and today <= d <= deadline

        return self.list(
            filters={'next_calibration': due},
            sort=SortSpec('next_calibration'),
        )

    def find_overdue_calibration(self) -> List[Dict[str, Any]]:
        """返回已超过校准期限的设备（next_calibration < today）。"""
        today = datetime.now().date()

        def overdue(next_cal: Any) -> bool:
            if not next_cal:
                return False
            d: Optional[date] = None
            if isinstance(next_cal, date) and not isinstance(next_cal, datetime):
                d = next_cal
            elif isinstance(next_cal, datetime):
                d = next_cal.date()
            elif isinstance(next_cal, str):
                try:
                    d = datetime.strptime(next_cal[:10], '%Y-%m-%d').date()
                except Exception:
                    return False
            return d is not None and d < today

        return self.list(filters={'next_calibration': overdue})

    def capacity_summary(self) -> Dict[str, Any]:
        """汇总全部仪器的产能情况。"""
        items = self.list()
        total_capacity = 0
        online_count = 0
        by_department: Dict[str, int] = {}
        by_manufacturer: Dict[str, int] = {}
        for it in items:
            dc = it.get('daily_capacity')
            if isinstance(dc, (int, float)):
                total_capacity += dc
            if it.get('status') == 'online':
                online_count += 1
            dept = it.get('department') or 'unknown'
            by_department[dept] = by_department.get(dept, 0) + 1
            mf = it.get('manufacturer') or 'unknown'
            by_manufacturer[mf] = by_manufacturer.get(mf, 0) + 1
        return {
            'total': len(items),
            'online': online_count,
            'total_daily_capacity': total_capacity,
            'by_department': by_department,
            'by_manufacturer': by_manufacturer,
        }

    def mark_offline(self, instrument_id: str, reason: Optional[str] = None) -> bool:
        """把设备置为离线状态。"""
        try:
            patch: Dict[str, Any] = {'status': 'offline'}
            if reason:
                patch['_last_offline_reason'] = reason
                patch['_last_offline_at'] = datetime.now().isoformat()
            self.update(instrument_id, patch)
            return True
        except Exception as e:
            logger.warning('mark_offline failed for %s: %s', instrument_id, e)
            return False

    def mark_online(self, instrument_id: str) -> bool:
        try:
            self.update(instrument_id, {'status': 'online'})
            return True
        except Exception as e:
            logger.warning('mark_online failed for %s: %s', instrument_id, e)
            return False

    def record_calibration(
        self,
        instrument_id: str,
        calibration_date: date,
        next_due: Optional[date] = None,
    ) -> bool:
        """记录一次校准。"""
        try:
            next_due = next_due or (calibration_date + timedelta(days=90))
            self.update(instrument_id, {
                'last_calibration': calibration_date.isoformat(),
                'next_calibration': next_due.isoformat(),
            })
            return True
        except Exception as e:
            logger.warning('record_calibration failed for %s: %s', instrument_id, e)
            return False

    def load_from_records(self, records: List[Dict[str, Any]]) -> int:
        count = 0
        for r in records:
            if not r.get('department_id'):
                continue
            try:
                self.create(r)
                count += 1
            except Exception as e:
                logger.debug('skip instrument %s: %s', r.get('department_id'), e)
        logger.info('loaded %d instruments into repository', count)
        return count
