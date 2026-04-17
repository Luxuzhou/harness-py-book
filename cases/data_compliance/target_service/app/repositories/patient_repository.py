"""
患者数据仓储。

承担患者个人信息（PII 敏感）的数据访问。本类本身不做脱敏，
脱敏责任由上层 Service 调用 `app.core.security.mask_pii()` 处理。
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from app.repositories.base import (
    BaseRepository, NotFoundError, Pagination, SortSpec,
)

logger = logging.getLogger(__name__)


class PatientRepository(BaseRepository[Dict[str, Any]]):
    """
    患者数据仓储。

    数据字段：
    - patient_id   (主键)
    - name         (姓名，PII)
    - id_card      (身份证，PII)
    - phone        (手机号，PII；可选)
    - gender       (male/female/other)
    - age          (年龄，整数)
    - birth_date   (出生日期，可选)
    - department   (所属科室)
    - diagnosis    (初步诊断)
    - created_at
    """

    def primary_key(self) -> str:
        return 'patient_id'

    def indexed_fields(self) -> List[str]:
        return ['patient_id', 'id_card', 'department']

    def list_by_department(
        self,
        department: str,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        """按科室列出患者。"""
        return self.list(
            filters={'department': department},
            sort=SortSpec('patient_id'),
            pagination=pagination,
        )

    def list_by_age_range(
        self,
        min_age: int,
        max_age: int,
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        """按年龄区间列出患者。"""
        return self.list(
            filters={'age': {'gte': min_age, 'lte': max_age}},
            sort=SortSpec('age', 'desc'),
            pagination=pagination,
        )

    def list_by_diagnosis_keywords(
        self,
        keywords: List[str],
        mode: str = 'any',
        pagination: Optional[Pagination] = None,
    ) -> List[Dict[str, Any]]:
        """
        按诊断关键词筛选。

        mode='any'：命中任一关键词即保留
        mode='all'：必须全部命中
        """
        def _match(diagnosis: Optional[str]) -> bool:
            if not diagnosis:
                return False
            hits = [kw for kw in keywords if kw in str(diagnosis)]
            if mode == 'all':
                return len(hits) == len(keywords)
            return bool(hits)

        return self.list(
            filters={'diagnosis': _match},
            sort=SortSpec('patient_id'),
            pagination=pagination,
        )

    def find_by_id_card(self, id_card: str) -> Optional[Dict[str, Any]]:
        """按身份证号查找患者（身份证号为唯一索引字段）。"""
        return self.get_by_field('id_card', id_card)

    def find_duplicates_by_id_card(self) -> List[List[str]]:
        """
        扫描数据中是否有身份证号重复但 patient_id 不同的脏数据。
        返回：按 id_card 分组的 patient_id 列表。
        """
        groups: Dict[str, List[str]] = {}
        for item in self._store:
            if item.get('_deleted_at'):
                continue
            ic = item.get('id_card')
            pid = item.get('patient_id')
            if ic and pid:
                groups.setdefault(ic, []).append(pid)
        return [pids for pids in groups.values() if len(pids) > 1]

    def statistics(self) -> Dict[str, Any]:
        """统计患者画像摘要。"""
        items = self.list()
        total = len(items)
        if total == 0:
            return {'total': 0}

        by_gender: Dict[str, int] = {}
        by_department: Dict[str, int] = {}
        age_sum = 0
        age_count = 0
        age_buckets = {'0-17': 0, '18-39': 0, '40-59': 0, '60+': 0}

        for it in items:
            g = it.get('gender') or 'unknown'
            by_gender[g] = by_gender.get(g, 0) + 1

            d = it.get('department') or 'unknown'
            by_department[d] = by_department.get(d, 0) + 1

            age = it.get('age')
            if isinstance(age, (int, float)) and age >= 0:
                age_sum += age
                age_count += 1
                if age < 18:
                    age_buckets['0-17'] += 1
                elif age < 40:
                    age_buckets['18-39'] += 1
                elif age < 60:
                    age_buckets['40-59'] += 1
                else:
                    age_buckets['60+'] += 1

        avg_age = round(age_sum / age_count, 2) if age_count else None

        top_departments = dict(
            sorted(by_department.items(), key=lambda x: -x[1])[:10]
        )

        return {
            'total': total,
            'by_gender': by_gender,
            'by_department_top10': top_departments,
            'avg_age': avg_age,
            'age_distribution': age_buckets,
        }

    def calculate_birth_year_from_id_card(
        self,
        patient_id: str,
    ) -> Optional[int]:
        """从身份证号提取出生年份（如果记录里没有 birth_date）。

        中国大陆身份证号第 7-10 位是出生年份。
        """
        patient = self.get_by_id(patient_id)
        if not patient:
            return None
        id_card = patient.get('id_card')
        if not id_card or len(id_card) < 10:
            return None
        year_str = id_card[6:10]
        try:
            year = int(year_str)
            current = datetime.now().year
            if 1900 <= year <= current:
                return year
        except (ValueError, TypeError):
            return None
        return None

    def merge_duplicate(
        self,
        survivor_id: str,
        victim_id: str,
    ) -> Dict[str, Any]:
        """
        合并重复患者记录。保留 survivor，把 victim 软删除。

        业务场景：一个患者在不同科室登记了不同 patient_id，
        但身份证号相同——需要合并成同一人。
        """
        survivor = self.get_by_id(survivor_id)
        victim = self.get_by_id(victim_id)
        if not survivor:
            raise NotFoundError(f'survivor patient {survivor_id} not found')
        if not victim:
            raise NotFoundError(f'victim patient {victim_id} not found')
        if survivor.get('id_card') != victim.get('id_card'):
            logger.warning(
                'merging patients with different id_card: %s vs %s',
                survivor.get('id_card'), victim.get('id_card'),
            )
        # 合并策略：survivor 为主，victim 的非空字段补全 survivor 缺失的字段
        patch: Dict[str, Any] = {}
        for k, v in victim.items():
            if k.startswith('_'):
                continue
            if k == self.primary_key():
                continue
            if not survivor.get(k) and v:
                patch[k] = v
        patch['_merged_from'] = victim_id
        if patch:
            self.update(survivor_id, patch)
        self.delete(victim_id, soft=True)
        return self.get_by_id(survivor_id) or {}

    def load_from_records(self, records: List[Dict[str, Any]]) -> int:
        """从已解析的 patients.csv 结果集批量加载。"""
        count = 0
        for r in records:
            if not r.get('patient_id'):
                continue
            # 字段规范化
            age = r.get('age')
            if isinstance(age, str) and age.isdigit():
                r['age'] = int(age)
            try:
                self.create(r)
                count += 1
            except Exception as e:
                logger.debug('skip patient %s: %s', r.get('patient_id'), e)
        logger.info('loaded %d patients into repository', count)
        return count
