"""
动态过滤服务
处理复杂的嵌套过滤逻辑，将FilterGroup/SimulationFilters转换为SQL条件或内存过滤
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from app.models.schemas import (
    AgeFilter,
    DepartmentFilter,
    DiagnosisFilter,
    FilterGroup,
    FilterItem,
    FilterOperatorEnum,
    GenderEnum,
    MedicationFilter,
    SimulationFilters,
    SpecimenFilter,
    TimeRangeFilter,
)

logger = logging.getLogger(__name__)


class FilterEngine:
    """
    过滤引擎：将结构化过滤条件转换为SQL片段或内存过滤函数
    """

    def __init__(self):
        self._operator_map = {
            FilterOperatorEnum.EQ: "=",
            FilterOperatorEnum.NEQ: "!=",
            FilterOperatorEnum.GT: ">",
            FilterOperatorEnum.GTE: ">=",
            FilterOperatorEnum.LT: "<",
            FilterOperatorEnum.LTE: "<=",
            FilterOperatorEnum.LIKE: "LIKE",
            FilterOperatorEnum.NOT_LIKE: "NOT LIKE",
            FilterOperatorEnum.IS_NULL: "IS NULL",
            FilterOperatorEnum.IS_NOT_NULL: "IS NOT NULL",
        }
        print("[DEBUG] FilterEngine initialized")

    # ──────────────────────────────────────────────────────────
    # SQL条件生成
    # ──────────────────────────────────────────────────────────
    def filter_item_to_sql(self, item: FilterItem,
                           table_alias: str = "") -> str:
        """
        将单个过滤条件转换为SQL片段
        坏味道: SQL字符串拼接
        """
        field = f"{table_alias}.{item.field}" if table_alias else item.field
        op = item.operator

        if op == FilterOperatorEnum.IN:
            values = item.values or ([item.value] if item.value else [])
            vals_str = ", ".join(f"'{v}'" for v in values)
            return f"{field} IN ({vals_str})"

        elif op == FilterOperatorEnum.NOT_IN:
            values = item.values or ([item.value] if item.value else [])
            vals_str = ", ".join(f"'{v}'" for v in values)
            return f"{field} NOT IN ({vals_str})"

        elif op == FilterOperatorEnum.BETWEEN:
            if isinstance(item.value, (list, tuple)) and len(item.value) >= 2:
                return f"{field} BETWEEN {item.value[0]} AND {item.value[1]}"
            return f"{field} IS NOT NULL"

        elif op == FilterOperatorEnum.IS_NULL:
            return f"{field} IS NULL"

        elif op == FilterOperatorEnum.IS_NOT_NULL:
            return f"{field} IS NOT NULL"

        elif op == FilterOperatorEnum.LIKE:
            # 坏味道: 直接拼接用户输入
            val = item.value
            if not item.case_sensitive:
                return f"lower({field}) LIKE lower('%{val}%')"
            return f"{field} LIKE '%{val}%'"

        elif op == FilterOperatorEnum.NOT_LIKE:
            val = item.value
            return f"{field} NOT LIKE '%{val}%'"

        else:
            sql_op = self._operator_map.get(op, "=")
            val = item.value
            if isinstance(val, str):
                return f"{field} {sql_op} '{val}'"
            elif isinstance(val, bool):
                return f"{field} {sql_op} {1 if val else 0}"
            elif val is None:
                return f"{field} IS NULL"
            else:
                return f"{field} {sql_op} {val}"

    def filter_group_to_sql(self, group: FilterGroup,
                            table_alias: str = "") -> str:
        """
        将过滤组递归转换为SQL片段
        """
        parts = []
        for f in group.filters:
            if isinstance(f, FilterItem):
                parts.append(self.filter_item_to_sql(f, table_alias))
            elif isinstance(f, FilterGroup):
                sub_sql = self.filter_group_to_sql(f, table_alias)
                if sub_sql:
                    parts.append(f"({sub_sql})")

        if not parts:
            return ""

        joiner = f" {group.logic} "
        return joiner.join(parts)

    def simulation_filters_to_sql(self, filters: SimulationFilters,
                                   patient_alias: str = "p",
                                   result_alias: str = "lr"
                                   ) -> List[str]:
        """
        将SimulationFilters转换为SQL条件列表
        """
        conditions = []

        # 性别
        if filters.gender:
            conditions.append(
                f"{patient_alias}.gender = '{filters.gender.value}'"
            )

        # 年龄
        if filters.age:
            if filters.age.min_age is not None:
                conditions.append(
                    f"{patient_alias}.age >= {filters.age.min_age}"
                )
            if filters.age.max_age is not None:
                conditions.append(
                    f"{patient_alias}.age <= {filters.age.max_age}"
                )

        # 科室
        if filters.department:
            if filters.department.include:
                dept_str = ", ".join(
                    f"'{d}'" for d in filters.department.include
                )
                conditions.append(
                    f"{patient_alias}.department IN ({dept_str})"
                )
            if filters.department.exclude:
                dept_str = ", ".join(
                    f"'{d}'" for d in filters.department.exclude
                )
                conditions.append(
                    f"{patient_alias}.department NOT IN ({dept_str})"
                )

        # 诊断
        if filters.diagnosis:
            if filters.diagnosis.include_keywords:
                diag_parts = []
                for kw in filters.diagnosis.include_keywords:
                    diag_parts.append(
                        f"{patient_alias}.diagnosis LIKE '%{kw}%'"
                    )
                conditions.append("(" + " OR ".join(diag_parts) + ")")

            if filters.diagnosis.exclude_keywords:
                for kw in filters.diagnosis.exclude_keywords:
                    conditions.append(
                        f"{patient_alias}.diagnosis NOT LIKE '%{kw}%'"
                    )

            if filters.diagnosis.icd_codes:
                icd_str = ", ".join(
                    f"'{c}'" for c in filters.diagnosis.icd_codes
                )
                conditions.append(
                    f"{patient_alias}.icd_code IN ({icd_str})"
                )

        # 标本
        if filters.specimen:
            if filters.specimen.specimen_types:
                st_str = ", ".join(
                    f"'{st.value}'" for st in filters.specimen.specimen_types
                )
                conditions.append(
                    f"{result_alias}.specimen_type IN ({st_str})"
                )

        # 时间范围
        if filters.time_range:
            tr = filters.time_range
            if tr.start_date:
                conditions.append(
                    f"{result_alias}.visit_date >= "
                    f"'{tr.start_date.strftime('%Y-%m-%d %H:%M:%S')}'"
                )
            if tr.end_date:
                conditions.append(
                    f"{result_alias}.visit_date <= "
                    f"'{tr.end_date.strftime('%Y-%m-%d %H:%M:%S')}'"
                )
            if tr.recent_days:
                conditions.append(
                    f"{result_alias}.visit_date >= "
                    f"now() - INTERVAL {tr.recent_days} DAY"
                )

        # 排除重复患者
        if filters.exclude_repeat_patients:
            conditions.append(
                f"{result_alias}.patient_id IN ("
                f"SELECT patient_id FROM lab_data.{result_alias} "
                f"GROUP BY patient_id HAVING count() = 1)"
            )

        # 自定义过滤
        if filters.custom_filters:
            custom_sql = self.filter_group_to_sql(filters.custom_filters)
            if custom_sql:
                conditions.append(f"({custom_sql})")

        print(f"[DEBUG] Generated {len(conditions)} filter conditions")
        logger.info(f"过滤条件生成: {len(conditions)}个条件")
        return conditions

    # ──────────────────────────────────────────────────────────
    # 内存过滤（用于CSV/小数据集）
    # ──────────────────────────────────────────────────────────
    def apply_filters_in_memory(
        self,
        records: List[Dict[str, Any]],
        filters: SimulationFilters,
    ) -> List[Dict[str, Any]]:
        """
        在内存中应用过滤条件
        """
        result = records

        # 性别过滤
        if filters.gender:
            gender_val = filters.gender.value
            result = [
                r for r in result
                if self._match_gender(r.get("gender"), gender_val)
            ]

        # 年龄过滤
        if filters.age:
            result = self._filter_by_age(result, filters.age)

        # 科室过滤
        if filters.department:
            result = self._filter_by_department(result, filters.department)

        # 诊断过滤
        if filters.diagnosis:
            result = self._filter_by_diagnosis(result, filters.diagnosis)

        # 用药过滤
        if filters.medication:
            result = self._filter_by_medication(result, filters.medication)

        # 标本过滤
        if filters.specimen:
            result = self._filter_by_specimen(result, filters.specimen)

        # 时间范围过滤
        if filters.time_range:
            result = self._filter_by_time(result, filters.time_range)

        # 排除重复患者
        if filters.exclude_repeat_patients:
            seen_patients = set()
            unique_result = []
            for r in result:
                pid = r.get("patient_id")
                if pid not in seen_patients:
                    seen_patients.add(pid)
                    unique_result.append(r)
            result = unique_result

        print(f"[DEBUG] Memory filter: {len(records)} -> {len(result)}")
        logger.info(f"内存过滤: {len(records)} -> {len(result)} 条记录")
        return result

    def _match_gender(self, value: Any, target: str) -> bool:
        """匹配性别"""
        if value is None:
            return False
        val_str = str(value).lower().strip()
        target_lower = target.lower()

        gender_mapping = {
            "male": ["male", "m", "男", "男性", "1"],
            "female": ["female", "f", "女", "女性", "2"],
        }

        target_variants = gender_mapping.get(target_lower, [target_lower])
        return val_str in target_variants

    def _filter_by_age(self, records: List[Dict[str, Any]],
                       age_filter: AgeFilter) -> List[Dict[str, Any]]:
        """按年龄过滤"""
        result = []
        for r in records:
            age = r.get("age")
            if age is None:
                continue
            try:
                age_int = int(str(age).rstrip("岁YyMmDd "))
            except (ValueError, TypeError):
                continue

            if age_filter.min_age is not None and age_int < age_filter.min_age:
                continue
            if age_filter.max_age is not None and age_int > age_filter.max_age:
                continue
            result.append(r)
        return result

    def _filter_by_department(self, records: List[Dict[str, Any]],
                              dept_filter: DepartmentFilter
                              ) -> List[Dict[str, Any]]:
        """按科室过滤"""
        result = []
        include_set = set(dept_filter.include) if dept_filter.include else None
        exclude_set = set(dept_filter.exclude) if dept_filter.exclude else set()

        for r in records:
            dept = r.get("department", "")
            if include_set and dept not in include_set:
                continue
            if dept in exclude_set:
                continue
            result.append(r)
        return result

    def _filter_by_diagnosis(self, records: List[Dict[str, Any]],
                             diag_filter: DiagnosisFilter
                             ) -> List[Dict[str, Any]]:
        """按诊断过滤"""
        result = []
        for r in records:
            diagnosis = r.get("diagnosis", "")

            # 排除关键词
            if diag_filter.exclude_keywords:
                if any(kw in diagnosis for kw in diag_filter.exclude_keywords):
                    continue

            # 包含关键词（OR逻辑）
            if diag_filter.include_keywords:
                if not any(kw in diagnosis
                           for kw in diag_filter.include_keywords):
                    continue

            result.append(r)
        return result

    def _filter_by_medication(self, records: List[Dict[str, Any]],
                              med_filter: MedicationFilter
                              ) -> List[Dict[str, Any]]:
        """按用药过滤"""
        result = []
        for r in records:
            medications = r.get("medications", [])
            if isinstance(medications, str):
                medications = [m.strip() for m in medications.split(",")]

            # 排除用药
            if med_filter.exclude_medications:
                if any(m in medications
                       for m in med_filter.exclude_medications):
                    continue

            # 包含用药
            if med_filter.include_medications:
                if not any(m in medications
                           for m in med_filter.include_medications):
                    continue

            result.append(r)
        return result

    def _filter_by_specimen(self, records: List[Dict[str, Any]],
                            spec_filter: SpecimenFilter
                            ) -> List[Dict[str, Any]]:
        """按标本过滤"""
        result = []
        allowed_types = set(
            st.value for st in spec_filter.specimen_types
        ) if spec_filter.specimen_types else None

        for r in records:
            specimen_type = r.get("specimen_type", "")

            if allowed_types and specimen_type not in allowed_types:
                continue
            if spec_filter.exclude_hemolysis and r.get("hemolysis", False):
                continue
            if spec_filter.exclude_lipemia and r.get("lipemia", False):
                continue
            if spec_filter.exclude_icterus and r.get("icterus", False):
                continue

            result.append(r)
        return result

    def _filter_by_time(self, records: List[Dict[str, Any]],
                        time_filter: TimeRangeFilter
                        ) -> List[Dict[str, Any]]:
        """按时间范围过滤"""
        result = []

        start = time_filter.start_date
        end = time_filter.end_date

        if time_filter.recent_days:
            end = datetime.now()
            start = end - timedelta(days=time_filter.recent_days)

        for r in records:
            visit_date = r.get("visit_date")
            if visit_date is None:
                continue

            if isinstance(visit_date, str):
                try:
                    visit_date = datetime.fromisoformat(
                        visit_date.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    try:
                        visit_date = datetime.strptime(
                            visit_date, "%Y-%m-%d %H:%M:%S"
                        )
                    except (ValueError, TypeError):
                        continue

            if start and visit_date < start:
                continue
            if end and visit_date > end:
                continue

            result.append(r)
        return result

    # ──────────────────────────────────────────────────────────
    # 自定义过滤条件构建
    # ──────────────────────────────────────────────────────────
    def apply_filter_group_in_memory(
        self,
        records: List[Dict[str, Any]],
        group: FilterGroup,
    ) -> List[Dict[str, Any]]:
        """在内存中应用FilterGroup过滤"""
        if not group.filters:
            return records

        if group.logic == "AND":
            result = records
            for f in group.filters:
                if isinstance(f, FilterItem):
                    result = self._apply_single_filter(result, f)
                elif isinstance(f, FilterGroup):
                    result = self.apply_filter_group_in_memory(result, f)
            return result

        elif group.logic == "OR":
            combined = set()
            record_map = {id(r): r for r in records}

            for f in group.filters:
                if isinstance(f, FilterItem):
                    matched = self._apply_single_filter(records, f)
                elif isinstance(f, FilterGroup):
                    matched = self.apply_filter_group_in_memory(records, f)
                else:
                    matched = []

                for r in matched:
                    combined.add(id(r))

            return [record_map[rid] for rid in combined if rid in record_map]

        return records

    def _apply_single_filter(self, records: List[Dict[str, Any]],
                             item: FilterItem) -> List[Dict[str, Any]]:
        """应用单个过滤条件到内存记录"""
        result = []
        for r in records:
            val = r.get(item.field)
            if self._evaluate_condition(val, item.operator, item.value,
                                        item.values, item.case_sensitive):
                result.append(r)
        return result

    def _evaluate_condition(self, actual: Any,
                            operator: FilterOperatorEnum,
                            expected: Any,
                            expected_list: Optional[List[Any]],
                            case_sensitive: bool) -> bool:
        """评估单个条件"""
        try:
            if operator == FilterOperatorEnum.IS_NULL:
                return actual is None
            if operator == FilterOperatorEnum.IS_NOT_NULL:
                return actual is not None

            if actual is None:
                return False

            # 字符串比较的大小写处理
            if not case_sensitive and isinstance(actual, str):
                actual = actual.lower()
                if isinstance(expected, str):
                    expected = expected.lower()

            if operator == FilterOperatorEnum.EQ:
                return actual == expected
            elif operator == FilterOperatorEnum.NEQ:
                return actual != expected
            elif operator == FilterOperatorEnum.GT:
                return float(actual) > float(expected)
            elif operator == FilterOperatorEnum.GTE:
                return float(actual) >= float(expected)
            elif operator == FilterOperatorEnum.LT:
                return float(actual) < float(expected)
            elif operator == FilterOperatorEnum.LTE:
                return float(actual) <= float(expected)
            elif operator == FilterOperatorEnum.IN:
                values = expected_list or []
                return actual in values
            elif operator == FilterOperatorEnum.NOT_IN:
                values = expected_list or []
                return actual not in values
            elif operator == FilterOperatorEnum.LIKE:
                pattern = str(expected).replace("%", ".*")
                return bool(re.search(pattern, str(actual)))
            elif operator == FilterOperatorEnum.NOT_LIKE:
                pattern = str(expected).replace("%", ".*")
                return not bool(re.search(pattern, str(actual)))
            elif operator == FilterOperatorEnum.BETWEEN:
                if isinstance(expected, (list, tuple)) and len(expected) >= 2:
                    return float(expected[0]) <= float(actual) <= float(expected[1])
                return True

        except (ValueError, TypeError):
            # 坏味道: 静默吞掉
            pass

        return False


class FilterService:
    """
    过滤服务：管理过滤引擎和过滤预设
    """

    def __init__(self):
        self.engine = FilterEngine()
        self._presets: Dict[str, SimulationFilters] = {}
        self._init_default_presets()
        print("[DEBUG] FilterService initialized")
        logger.info("FilterService初始化完成")

    def _init_default_presets(self):
        """初始化默认过滤预设"""
        # 常规门诊
        self._presets["outpatient"] = SimulationFilters(
            department=DepartmentFilter(
                include=["门诊", "急诊"],
                exclude=["ICU", "新生儿科"],
            ),
            age=AgeFilter(min_age=18, max_age=80),
        )

        # 排除特殊科室
        self._presets["exclude_special"] = SimulationFilters(
            department=DepartmentFilter(
                exclude=["ICU", "新生儿科", "肾内科", "肿瘤科", "血液科"],
            ),
            diagnosis=DiagnosisFilter(
                exclude_keywords=["肾衰", "透析", "化疗", "白血病"],
            ),
        )

        # 成年男性
        self._presets["adult_male"] = SimulationFilters(
            gender=GenderEnum.MALE,
            age=AgeFilter(min_age=18, max_age=65),
        )

        # 成年女性
        self._presets["adult_female"] = SimulationFilters(
            gender=GenderEnum.FEMALE,
            age=AgeFilter(min_age=18, max_age=65),
        )

    def get_preset(self, name: str) -> Optional[SimulationFilters]:
        """获取过滤预设"""
        return self._presets.get(name)

    def list_presets(self) -> List[str]:
        """列出所有预设名称"""
        return list(self._presets.keys())

    def save_preset(self, name: str, filters: SimulationFilters) -> None:
        """保存过滤预设"""
        self._presets[name] = filters
        logger.info(f"过滤预设已保存: {name}")

    def filter_to_sql(self, filters: SimulationFilters,
                      patient_alias: str = "p",
                      result_alias: str = "lr") -> List[str]:
        """将过滤条件转换为SQL条件列表"""
        return self.engine.simulation_filters_to_sql(
            filters, patient_alias, result_alias
        )

    def filter_in_memory(self, records: List[Dict[str, Any]],
                         filters: SimulationFilters
                         ) -> List[Dict[str, Any]]:
        """在内存中应用过滤"""
        return self.engine.apply_filters_in_memory(records, filters)
