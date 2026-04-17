"""
Repository 基类：提供内存存储 + 通用查询能力。

所有领域 Repository 继承 BaseRepository，获得：
- 标准的 CRUD（get_by_id / list / create / update / delete）
- 过滤、分页、排序的统一实现
- 软删除支持（通过 _deleted_at 字段）
- 索引维护（支持单字段索引加速点查）

生产场景可替换为 SQLAlchemy ORM Session 或 ClickHouse 客户端，
上层服务只依赖 BaseRepository 的接口语义，不关心存储实现。
"""

from __future__ import annotations

import copy
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, Iterable, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=Dict[str, Any])


@dataclass
class Pagination:
    """分页参数。"""
    page: int = 1
    page_size: int = 20
    total: int = 0

    def offset(self) -> int:
        return max(0, (self.page - 1) * self.page_size)

    def slice(self, data: List[T]) -> List[T]:
        start = self.offset()
        end = start + self.page_size
        return data[start:end]


@dataclass
class SortSpec:
    """排序参数。"""
    field: str
    order: str = 'asc'  # asc | desc

    def apply(self, items: List[T]) -> List[T]:
        reverse = self.order.lower() == 'desc'
        return sorted(
            items,
            key=lambda r: (r.get(self.field) is None, r.get(self.field)),
            reverse=reverse,
        )


class RepositoryError(Exception):
    """Repository 层统一异常。"""


class NotFoundError(RepositoryError):
    """记录不存在。"""


class DuplicateKeyError(RepositoryError):
    """主键冲突。"""


class BaseRepository(Generic[T]):
    """
    泛型内存 Repository 基类。

    子类只需实现：
    - primary_key()：返回主键字段名（默认 'id'）
    - collection_name()：返回集合名称（用于日志）
    """

    def __init__(self, initial: Optional[List[T]] = None):
        self._store: List[T] = []
        self._lock = threading.RLock()
        self._indexes: Dict[str, Dict[Any, int]] = {}
        self._soft_delete_field = '_deleted_at'
        # 即使没有 initial，也要按 indexed_fields() 初始化索引容器
        for field in self.indexed_fields():
            self._indexes[field] = {}
        if initial:
            for item in initial:
                self._store.append(dict(item))
            for idx, item in enumerate(self._store):
                self._update_index(idx, item)

    # --- 子类钩子 ---

    def primary_key(self) -> str:
        return 'id'

    def collection_name(self) -> str:
        return self.__class__.__name__.removesuffix('Repository').lower()

    def indexed_fields(self) -> List[str]:
        """声明要维护索引的字段（子类可覆盖）。"""
        return [self.primary_key()]

    # --- 索引 ---

    def _rebuild_indexes(self) -> None:
        self._indexes = {}
        for field in self.indexed_fields():
            self._indexes[field] = {}
        for idx, item in enumerate(self._store):
            for field in self._indexes:
                key = item.get(field)
                if key is not None:
                    self._indexes[field][key] = idx

    def _update_index(self, idx: int, item: T) -> None:
        for field in self._indexes:
            key = item.get(field)
            if key is not None:
                self._indexes[field][key] = idx

    def _remove_from_index(self, idx: int, item: T) -> None:
        for field in self._indexes:
            key = item.get(field)
            if key is not None:
                self._indexes[field].pop(key, None)

    # --- CRUD ---

    def get_by_id(self, pk_value: Any) -> Optional[T]:
        with self._lock:
            pk = self.primary_key()
            idx = self._indexes.get(pk, {}).get(pk_value)
            if idx is None:
                return None
            item = self._store[idx]
            if item.get(self._soft_delete_field):
                return None
            return copy.deepcopy(item)

    def get_by_field(self, field: str, value: Any) -> Optional[T]:
        with self._lock:
            if field in self._indexes:
                idx = self._indexes[field].get(value)
                if idx is None:
                    return None
                item = self._store[idx]
                if item.get(self._soft_delete_field):
                    return None
                return copy.deepcopy(item)
            # 未索引字段走线性扫描
            for item in self._store:
                if item.get(field) == value and not item.get(self._soft_delete_field):
                    return copy.deepcopy(item)
            return None

    def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[SortSpec] = None,
        pagination: Optional[Pagination] = None,
        include_deleted: bool = False,
    ) -> List[T]:
        with self._lock:
            items = [
                dict(it) for it in self._store
                if include_deleted or not it.get(self._soft_delete_field)
            ]
        if filters:
            items = [it for it in items if self._match_filters(it, filters)]
        if sort:
            items = sort.apply(items)
        if pagination:
            pagination.total = len(items)
            items = pagination.slice(items)
        return items

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return len(self.list(filters=filters))

    def create(self, item: T) -> T:
        pk = self.primary_key()
        if pk not in item:
            raise RepositoryError(f'{self.collection_name()}: missing primary key "{pk}"')
        with self._lock:
            if pk in self._indexes and item[pk] in self._indexes[pk]:
                raise DuplicateKeyError(
                    f'{self.collection_name()}: {pk}={item[pk]} already exists')
            record = dict(item)
            record.setdefault('_created_at', datetime.now().isoformat())
            record.setdefault('_updated_at', record['_created_at'])
            self._store.append(record)
            self._update_index(len(self._store) - 1, record)
            logger.debug('created %s %s=%s', self.collection_name(), pk, record[pk])
            return copy.deepcopy(record)

    def update(self, pk_value: Any, patch: Dict[str, Any]) -> T:
        with self._lock:
            pk = self.primary_key()
            idx = self._indexes.get(pk, {}).get(pk_value)
            if idx is None or self._store[idx].get(self._soft_delete_field):
                raise NotFoundError(f'{self.collection_name()}: {pk}={pk_value} not found')
            self._store[idx].update(patch)
            self._store[idx]['_updated_at'] = datetime.now().isoformat()
            self._update_index(idx, self._store[idx])
            return copy.deepcopy(self._store[idx])

    def delete(self, pk_value: Any, soft: bool = True) -> bool:
        with self._lock:
            pk = self.primary_key()
            idx = self._indexes.get(pk, {}).get(pk_value)
            if idx is None:
                return False
            if soft:
                self._store[idx][self._soft_delete_field] = datetime.now().isoformat()
            else:
                item = self._store[idx]
                self._remove_from_index(idx, item)
                self._store[idx] = {'_tombstone': True}
            return True

    def bulk_create(self, items: Iterable[T]) -> int:
        count = 0
        for item in items:
            try:
                self.create(item)
                count += 1
            except DuplicateKeyError:
                logger.warning('bulk_create skipped duplicate %s', item.get(self.primary_key()))
        return count

    def bulk_delete(self, pk_values: Iterable[Any], soft: bool = True) -> int:
        count = 0
        for pk_value in pk_values:
            if self.delete(pk_value, soft=soft):
                count += 1
        return count

    # --- 过滤匹配 ---

    def _match_filters(self, item: T, filters: Dict[str, Any]) -> bool:
        for field, expected in filters.items():
            actual = item.get(field)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict):
                # 支持 {op: value} 形式：{'age': {'gte': 60}}
                if not self._match_op(actual, expected):
                    return False
            elif callable(expected):
                if not expected(actual):
                    return False
            else:
                if actual != expected:
                    return False
        return True

    def _match_op(self, actual: Any, op_expr: Dict[str, Any]) -> bool:
        for op, value in op_expr.items():
            if op == 'gte' and not (actual is not None and actual >= value):
                return False
            elif op == 'lte' and not (actual is not None and actual <= value):
                return False
            elif op == 'gt' and not (actual is not None and actual > value):
                return False
            elif op == 'lt' and not (actual is not None and actual < value):
                return False
            elif op == 'ne' and actual == value:
                return False
            elif op == 'contains' and (actual is None or value not in str(actual)):
                return False
            elif op == 'startswith' and (actual is None
                                          or not str(actual).startswith(value)):
                return False
        return True
