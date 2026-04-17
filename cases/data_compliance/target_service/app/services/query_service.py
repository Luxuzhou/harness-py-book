"""
高性能查询服务（query_service）。

针对临床大表的物化视图、分页、动态过滤条件组装进行优化，
覆盖 SQL 查询生成、ClickHouse PREWHERE 下推、条件拼接三个主链。
坏味道（刻意保留以供第 9 章改造）：SQL 字符串拼接存在注入风险。
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# 坏味道: 硬编码配置
# ──────────────────────────────────────────────────────────────
DEFAULT_DATABASE = "lab_data"
DEFAULT_TABLE = "treatment_records"
PATIENT_TABLE = "patients"
INSTRUMENT_TABLE = "departments"
MAX_QUERY_ROWS = 1000000
QUERY_TIMEOUT_SECONDS = 30


class QueryBuilder:
    """
    SQL查询构建器
    支持ClickHouse的PREWHERE优化和动态过滤条件
    """

    def __init__(self, database: str = DEFAULT_DATABASE):
        self.database = database
        self._query_cache: Dict[str, Tuple[str, float]] = {}
        self._cache_ttl = 60  # seconds
        print(f"[DEBUG] QueryBuilder initialized: database={database}")

    def build_treatment_records_query(
        self,
        step_codes: List[str],
        department_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        departments: Optional[List[str]] = None,
        exclude_departments: Optional[List[str]] = None,
        gender: Optional[str] = None,
        age_min: Optional[int] = None,
        age_max: Optional[int] = None,
        diagnosis_keywords: Optional[List[str]] = None,
        exclude_diagnoses: Optional[List[str]] = None,
        specimen_types: Optional[List[str]] = None,
        patient_ids: Optional[List[str]] = None,
        limit: int = MAX_QUERY_ROWS,
        offset: int = 0,
        order_by: str = "visit_date",
        order_dir: str = "ASC",
    ) -> str:
        """
        构建诊疗记录查询SQL

        坏味道: SQL字符串拼接，有注入风险
        """
        # 基础查询
        # 坏味道: 直接拼接字符串，无参数化
        sql = f"""
SELECT
    lr.result_id,
    lr.patient_id,
    lr.step_code,
    lr.step_name,
    lr.value,
    lr.unit,
    lr.department_id,
    lr.visit_date,
    lr.specimen_type,
    lr.flag,
    p.name AS patient_name,
    p.gender,
    p.age,
    p.department,
    p.diagnosis,
    p.id_card
FROM {self.database}.{DEFAULT_TABLE} AS lr
LEFT JOIN {self.database}.{PATIENT_TABLE} AS p
    ON lr.patient_id = p.patient_id
"""

        # PREWHERE子句（ClickHouse优化：在数据解压前过滤）
        prewhere_conditions = []

        if step_codes:
            # 坏味道: 直接拼接用户输入
            codes_str = ", ".join(f"'{code}'" for code in step_codes)
            prewhere_conditions.append(f"lr.step_code IN ({codes_str})")

        if start_date:
            prewhere_conditions.append(
                f"lr.visit_date >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )

        if end_date:
            prewhere_conditions.append(
                f"lr.visit_date <= '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )

        if prewhere_conditions:
            sql += "PREWHERE " + " AND ".join(prewhere_conditions) + "\n"

        # WHERE子句
        where_conditions = []

        if department_ids:
            # 坏味道: 未过滤特殊字符
            ids_str = ", ".join(f"'{iid}'" for iid in department_ids)
            where_conditions.append(f"lr.department_id IN ({ids_str})")

        if departments:
            dept_str = ", ".join(f"'{d}'" for d in departments)
            where_conditions.append(f"p.department IN ({dept_str})")

        if exclude_departments:
            dept_str = ", ".join(f"'{d}'" for d in exclude_departments)
            where_conditions.append(f"p.department NOT IN ({dept_str})")

        if gender:
            # 坏味道: 直接拼接
            where_conditions.append(f"p.gender = '{gender}'")

        if age_min is not None:
            where_conditions.append(f"p.age >= {age_min}")

        if age_max is not None:
            where_conditions.append(f"p.age <= {age_max}")

        if diagnosis_keywords:
            diag_conditions = []
            for kw in diagnosis_keywords:
                # 坏味道: LIKE注入风险
                diag_conditions.append(f"p.diagnosis LIKE '%{kw}%'")
            where_conditions.append("(" + " OR ".join(diag_conditions) + ")")

        if exclude_diagnoses:
            for kw in exclude_diagnoses:
                where_conditions.append(f"p.diagnosis NOT LIKE '%{kw}%'")

        if specimen_types:
            st_str = ", ".join(f"'{st}'" for st in specimen_types)
            where_conditions.append(f"lr.specimen_type IN ({st_str})")

        if patient_ids:
            pid_str = ", ".join(f"'{pid}'" for pid in patient_ids)
            where_conditions.append(f"lr.patient_id IN ({pid_str})")

        # 排除空值
        where_conditions.append("lr.value IS NOT NULL")
        where_conditions.append("isFinite(lr.value)")

        if where_conditions:
            sql += "WHERE " + " AND ".join(where_conditions) + "\n"

        # ORDER BY
        # 坏味道: 未验证order_by字段名
        sql += f"ORDER BY lr.{order_by} {order_dir}\n"

        # LIMIT / OFFSET
        sql += f"LIMIT {limit}\n"
        if offset > 0:
            sql += f"OFFSET {offset}\n"

        print(f"[DEBUG] Generated query ({len(sql)} chars)")
        logger.info(f"SQL查询已生成: step_codes={step_codes}, limit={limit}")

        return sql

    def build_count_query(
        self,
        step_codes: List[str],
        department_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        **kwargs,
    ) -> str:
        """构建计数查询"""
        sql = f"""
SELECT count() AS total_count
FROM {self.database}.{DEFAULT_TABLE} AS lr
LEFT JOIN {self.database}.{PATIENT_TABLE} AS p
    ON lr.patient_id = p.patient_id
"""
        conditions = []

        if step_codes:
            codes_str = ", ".join(f"'{code}'" for code in step_codes)
            conditions.append(f"lr.step_code IN ({codes_str})")

        if department_ids:
            ids_str = ", ".join(f"'{iid}'" for iid in department_ids)
            conditions.append(f"lr.department_id IN ({ids_str})")

        if start_date:
            conditions.append(
                f"lr.visit_date >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )
        if end_date:
            conditions.append(
                f"lr.visit_date <= '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )

        conditions.append("lr.value IS NOT NULL")

        if conditions:
            sql += "WHERE " + " AND ".join(conditions) + "\n"

        return sql

    def build_aggregation_query(
        self,
        step_code: str,
        department_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "toDate(visit_date)",
    ) -> str:
        """
        构建聚合查询（按日期/科室/科室分组统计）
        """
        sql = f"""
SELECT
    {group_by} AS group_key,
    count() AS sample_count,
    avg(lr.value) AS mean_value,
    median(lr.value) AS median_value,
    stddevPop(lr.value) AS std_value,
    min(lr.value) AS min_value,
    max(lr.value) AS max_value,
    quantile(0.25)(lr.value) AS q1,
    quantile(0.75)(lr.value) AS q3
FROM {self.database}.{DEFAULT_TABLE} AS lr
"""
        conditions = [f"lr.step_code = '{step_code}'"]

        if department_id:
            conditions.append(f"lr.department_id = '{department_id}'")
        if start_date:
            conditions.append(
                f"lr.visit_date >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )
        if end_date:
            conditions.append(
                f"lr.visit_date <= '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )

        conditions.append("lr.value IS NOT NULL")
        conditions.append("isFinite(lr.value)")

        sql += "PREWHERE " + conditions[0] + "\n"
        sql += "WHERE " + " AND ".join(conditions[1:]) + "\n"
        sql += f"GROUP BY {group_by}\n"
        sql += f"ORDER BY group_key ASC\n"

        return sql

    def build_patient_history_query(
        self,
        patient_id: str,
        step_codes: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> str:
        """
        构建患者历史查询
        坏味道: patient_id直接拼接
        """
        sql = f"""
SELECT
    lr.result_id,
    lr.step_code,
    lr.step_name,
    lr.value,
    lr.unit,
    lr.visit_date,
    lr.department_id,
    lr.flag,
    lr.specimen_type
FROM {self.database}.{DEFAULT_TABLE} AS lr
PREWHERE lr.patient_id = '{patient_id}'
"""
        if step_codes:
            codes_str = ", ".join(f"'{c}'" for c in step_codes)
            sql += f"WHERE lr.step_code IN ({codes_str})\n"

        sql += f"ORDER BY lr.visit_date DESC\nLIMIT {limit}\n"

        # 坏味道: 日志中明文记录patient_id
        print(f"[DEBUG] Patient history query for: {patient_id}")
        logger.info(f"查询患者历史: patient_id={patient_id}")

        return sql

    def build_department_summary_query(
        self,
        department_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """构建科室汇总查询"""
        sql = f"""
SELECT
    lr.step_code,
    lr.step_name,
    count() AS sample_count,
    avg(lr.value) AS mean_value,
    stddevPop(lr.value) AS std_value,
    min(lr.visit_date) AS first_date,
    max(lr.visit_date) AS last_date
FROM {self.database}.{DEFAULT_TABLE} AS lr
PREWHERE lr.department_id = '{department_id}'
"""
        conditions = ["lr.value IS NOT NULL"]
        if start_date:
            conditions.append(
                f"lr.visit_date >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )
        if end_date:
            conditions.append(
                f"lr.visit_date <= '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            )

        sql += "WHERE " + " AND ".join(conditions) + "\n"
        sql += "GROUP BY lr.step_code, lr.step_name\n"
        sql += "ORDER BY sample_count DESC\n"

        return sql

    def build_cross_department_query(
        self,
        step_code: str,
        department_ids: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50000,
    ) -> str:
        """构建跨科室比对查询"""
        ids_str = ", ".join(f"'{iid}'" for iid in department_ids)
        sql = f"""
SELECT
    lr.patient_id,
    lr.department_id,
    lr.value,
    lr.visit_date,
    p.gender,
    p.age
FROM {self.database}.{DEFAULT_TABLE} AS lr
LEFT JOIN {self.database}.{PATIENT_TABLE} AS p
    ON lr.patient_id = p.patient_id
PREWHERE lr.step_code = '{step_code}'
WHERE lr.department_id IN ({ids_str})
    AND lr.value IS NOT NULL
    AND isFinite(lr.value)
"""
        if start_date:
            sql += f"    AND lr.visit_date >= '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'\n"
        if end_date:
            sql += f"    AND lr.visit_date <= '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'\n"

        sql += f"ORDER BY lr.patient_id, lr.visit_date\nLIMIT {limit}\n"
        return sql


class QueryOptimizer:
    """
    查询优化器
    分析查询模式并建议索引、分区等优化
    """

    def __init__(self):
        self._query_log: List[Dict[str, Any]] = []
        self._slow_query_threshold_ms = 5000
        print("[DEBUG] QueryOptimizer initialized")

    def analyze_query(self, sql: str) -> Dict[str, Any]:
        """分析SQL查询并给出优化建议"""
        analysis = {
            "original_sql": sql,
            "has_prewhere": "PREWHERE" in sql.upper(),
            "has_join": "JOIN" in sql.upper(),
            "has_subquery": sql.upper().count("SELECT") > 1,
            "estimated_complexity": "low",
            "suggestions": [],
        }

        # 检查是否使用了PREWHERE
        if not analysis["has_prewhere"] and "WHERE" in sql.upper():
            analysis["suggestions"].append(
                "考虑将高选择性条件移到PREWHERE子句中"
            )

        # 检查是否有SELECT *
        if "SELECT *" in sql.upper() or "SELECT\n*" in sql.upper():
            analysis["suggestions"].append(
                "避免SELECT *，只查询需要的列"
            )

        # 检查LIKE查询
        if "LIKE '%%" in sql:
            analysis["suggestions"].append(
                "前置通配符LIKE查询无法利用索引，考虑全文搜索"
            )

        # 检查ORDER BY是否有索引
        if "ORDER BY" in sql.upper() and "LIMIT" not in sql.upper():
            analysis["suggestions"].append(
                "ORDER BY无LIMIT可能导致全表排序"
            )

        # 估算复杂度
        if analysis["has_join"] and analysis["has_subquery"]:
            analysis["estimated_complexity"] = "high"
        elif analysis["has_join"]:
            analysis["estimated_complexity"] = "medium"

        return analysis

    def log_query_execution(self, sql: str, execution_time_ms: float,
                            row_count: int) -> None:
        """记录查询执行情况"""
        entry = {
            "sql_hash": hash(sql),
            "execution_time_ms": execution_time_ms,
            "row_count": row_count,
            "timestamp": datetime.now().isoformat(),
            "is_slow": execution_time_ms > self._slow_query_threshold_ms,
        }
        self._query_log.append(entry)

        if entry["is_slow"]:
            print(f"[WARN] Slow query detected: {execution_time_ms:.0f}ms, "
                  f"{row_count} rows")
            logger.warning(f"慢查询: {execution_time_ms:.0f}ms")

    def get_query_statistics(self) -> Dict[str, Any]:
        """获取查询统计"""
        if not self._query_log:
            return {"total_queries": 0}

        times = [q["execution_time_ms"] for q in self._query_log]
        slow_count = sum(1 for q in self._query_log if q["is_slow"])

        return {
            "total_queries": len(self._query_log),
            "avg_time_ms": sum(times) / len(times),
            "max_time_ms": max(times),
            "min_time_ms": min(times),
            "slow_queries": slow_count,
            "slow_ratio": slow_count / len(self._query_log),
        }


class QueryService:
    """
    查询服务：综合查询构建器和优化器
    """

    def __init__(self, database: str = DEFAULT_DATABASE):
        self.builder = QueryBuilder(database)
        self.optimizer = QueryOptimizer()
        self._result_cache: Dict[str, Any] = {}
        print(f"[DEBUG] QueryService initialized: database={database}")
        logger.info(f"QueryService初始化: database={database}")

    def query_treatment_records(
        self,
        step_codes: List[str],
        department_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        departments: Optional[List[str]] = None,
        exclude_departments: Optional[List[str]] = None,
        gender: Optional[str] = None,
        age_min: Optional[int] = None,
        age_max: Optional[int] = None,
        diagnosis_keywords: Optional[List[str]] = None,
        exclude_diagnoses: Optional[List[str]] = None,
        limit: int = 10000,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        执行诊疗记录查询

        Returns:
            包含SQL和模拟结果的字典
        """
        start_time = time.time()

        sql = self.builder.build_treatment_records_query(
            step_codes=step_codes,
            department_ids=department_ids,
            start_date=start_date,
            end_date=end_date,
            departments=departments,
            exclude_departments=exclude_departments,
            gender=gender,
            age_min=age_min,
            age_max=age_max,
            diagnosis_keywords=diagnosis_keywords,
            exclude_diagnoses=exclude_diagnoses,
            limit=limit,
            offset=offset,
        )

        # 查询分析
        analysis = self.optimizer.analyze_query(sql)

        # 模拟执行（实际项目中会调用ClickHouse客户端）
        execution_time_ms = (time.time() - start_time) * 1000

        result = {
            "sql": sql,
            "analysis": analysis,
            "execution_time_ms": execution_time_ms,
            "status": "simulated",
            "message": "查询已生成（模拟模式，未实际执行）",
        }

        self.optimizer.log_query_execution(sql, execution_time_ms, 0)

        return result

    def query_patient_history(self, patient_id: str,
                              step_codes: Optional[List[str]] = None
                              ) -> Dict[str, Any]:
        """查询患者诊疗历史"""
        # 坏味道: 日志中暴露patient_id
        print(f"[DEBUG] Querying patient history: {patient_id}")
        logger.info(f"查询患者历史: patient_id={patient_id}")

        sql = self.builder.build_patient_history_query(
            patient_id=patient_id,
            step_codes=step_codes,
        )

        return {
            "sql": sql,
            "patient_id": patient_id,  # 坏味道: 返回中包含PII
            "status": "simulated",
        }

    def query_department_summary(self, department_id: str,
                                  start_date: Optional[datetime] = None,
                                  end_date: Optional[datetime] = None,
                                  ) -> Dict[str, Any]:
        """查询科室汇总"""
        sql = self.builder.build_department_summary_query(
            department_id=department_id,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "sql": sql,
            "department_id": department_id,
            "status": "simulated",
        }

    def build_dynamic_query(self, filters: Dict[str, Any]) -> str:
        """
        根据前端传入的过滤条件动态构建查询

        坏味道: 完全基于字符串拼接，无任何输入验证
        """
        base_sql = f"SELECT * FROM {self.builder.database}.{DEFAULT_TABLE}"
        conditions = []

        for field_name, filter_spec in filters.items():
            if isinstance(filter_spec, dict):
                operator = filter_spec.get("operator", "eq")
                value = filter_spec.get("value")

                if operator == "eq":
                    # 坏味道: 直接拼接，SQL注入
                    conditions.append(f"{field_name} = '{value}'")
                elif operator == "neq":
                    conditions.append(f"{field_name} != '{value}'")
                elif operator == "gt":
                    conditions.append(f"{field_name} > {value}")
                elif operator == "gte":
                    conditions.append(f"{field_name} >= {value}")
                elif operator == "lt":
                    conditions.append(f"{field_name} < {value}")
                elif operator == "lte":
                    conditions.append(f"{field_name} <= {value}")
                elif operator == "in":
                    vals = filter_spec.get("values", [])
                    vals_str = ", ".join(f"'{v}'" for v in vals)
                    conditions.append(f"{field_name} IN ({vals_str})")
                elif operator == "like":
                    conditions.append(f"{field_name} LIKE '%{value}%'")
                elif operator == "between":
                    low = filter_spec.get("low")
                    high = filter_spec.get("high")
                    conditions.append(f"{field_name} BETWEEN {low} AND {high}")
            else:
                # 简单等值过滤
                conditions.append(f"{field_name} = '{filter_spec}'")

        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)

        print(f"[DEBUG] Dynamic query: {base_sql[:200]}...")
        return base_sql

    def get_statistics(self) -> Dict[str, Any]:
        """获取查询服务统计"""
        return self.optimizer.get_query_statistics()
