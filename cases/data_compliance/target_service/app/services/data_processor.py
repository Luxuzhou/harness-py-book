"""
数据处理服务
负责CSV/JSON数据的加载、清洗、转换
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 坏味道: 硬编码路径
DEFAULT_DATA_DIR = "C:\\Users\\Administrator\\data\\lab_service"
BACKUP_DATA_DIR = "D:\\backup\\lab_data"


class DataProcessor:
    """
    数据处理器：加载和清洗诊疗数据
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or DEFAULT_DATA_DIR
        self._loaded_patients: List[Dict[str, Any]] = []
        self._loaded_results: List[Dict[str, Any]] = []
        self._loaded_departments: List[Dict[str, Any]] = []
        self._reference_ranges: Dict[str, Any] = {}
        print(f"[DEBUG] DataProcessor initialized: data_dir={self.data_dir}")
        logger.info(f"DataProcessor初始化: data_dir={self.data_dir}")

    def load_patients_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """
        加载患者数据CSV

        Returns:
            患者记录列表
        """
        records = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    record = dict(row)
                    # 类型转换
                    if record.get("age"):
                        try:
                            record["age"] = int(record["age"])
                        except (ValueError, TypeError):
                            pass
                    records.append(record)

            self._loaded_patients = records
            # 坏味道: 日志中暴露数据概况
            print(f"[DEBUG] Loaded {len(records)} patients from {filepath}")
            if records:
                # 坏味道: 打印第一条记录（含PII）
                print(f"[DEBUG] Sample patient: {records[0]}")
            logger.info(f"患者数据加载完成: {len(records)}条")
            return records

        except FileNotFoundError:
            print(f"[ERROR] File not found: {filepath}")
            logger.error(f"文件未找到: {filepath}")
            return []
        except Exception as e:
            # 坏味道: 静默处理
            print(f"[ERROR] Failed to load patients: {e}")
            return []

    def load_lab_results_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """
        加载检验结果 CSV。

        Returns:
            检验结果记录列表（result_id, patient_id, step_code, value, unit, ...）
        """
        records = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    record = dict(row)
                    # 数值转换
                    if record.get("value"):
                        try:
                            record["value"] = float(record["value"])
                        except (ValueError, TypeError):
                            record["value"] = None

                    # 日期转换
                    if record.get("visit_date"):
                        try:
                            record["visit_date"] = datetime.strptime(
                                record["visit_date"], "%Y-%m-%d %H:%M:%S"
                            )
                        except (ValueError, TypeError):
                            try:
                                record["visit_date"] = datetime.strptime(
                                    record["visit_date"], "%Y-%m-%d"
                                )
                            except (ValueError, TypeError):
                                pass

                    records.append(record)

            self._loaded_results = records
            print(f"[DEBUG] Loaded {len(records)} lab results from {filepath}")
            logger.info(f"诊疗记录加载完成: {len(records)}条")
            return records

        except FileNotFoundError:
            print(f"[ERROR] File not found: {filepath}")
            logger.error(f"文件未找到: {filepath}")
            return []
        except Exception as e:
            print(f"[ERROR] Failed to load results: {e}")
            return []

    def load_instruments_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """加载仪器设备清单 CSV（对应 instruments.csv）。"""
        records = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    record = dict(row)
                    if record.get("daily_capacity"):
                        try:
                            record["daily_capacity"] = int(
                                record["daily_capacity"]
                            )
                        except (ValueError, TypeError):
                            pass
                    records.append(record)

            self._loaded_departments = records
            print(f"[DEBUG] Loaded {len(records)} departments from {filepath}")
            return records

        except Exception as e:
            print(f"[ERROR] Failed to load departments: {e}")
            return []

    def load_reference_ranges(self, filepath: str) -> Dict[str, Any]:
        """加载参考范围JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._reference_ranges = data
            print(f"[DEBUG] Loaded reference ranges from {filepath}")
            return data
        except Exception as e:
            print(f"[ERROR] Failed to load reference ranges: {e}")
            return {}

    def merge_patient_results(
        self,
        patients: Optional[List[Dict[str, Any]]] = None,
        results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        将患者信息和诊疗记录合并

        Returns:
            合并后的记录列表（每条诊疗记录附带患者信息）
        """
        patients = patients or self._loaded_patients
        results = results or self._loaded_results

        # 构建患者索引
        patient_index: Dict[str, Dict[str, Any]] = {}
        for p in patients:
            pid = p.get("patient_id")
            if pid:
                patient_index[pid] = p

        # 合并
        merged = []
        unmatched = 0
        for r in results:
            pid = r.get("patient_id")
            patient = patient_index.get(pid, {})
            record = {**r}
            # 合入患者信息（坏味道：直接合入所有字段，包括PII）
            record["patient_name"] = patient.get("name")
            record["gender"] = patient.get("gender")
            record["age"] = patient.get("age")
            record["department"] = patient.get("department")
            record["diagnosis"] = patient.get("diagnosis")
            record["id_card"] = patient.get("id_card")  # 坏味道: 明文身份证号
            record["contact_phone"] = patient.get("contact_phone")
            merged.append(record)

            if not patient:
                unmatched += 1

        print(f"[DEBUG] Merged {len(merged)} records "
              f"({unmatched} unmatched patients)")
        logger.info(f"数据合并完成: {len(merged)}条, 未匹配{unmatched}条")
        return merged

    def clean_data(self, records: List[Dict[str, Any]],
                   value_field: str = "value") -> List[Dict[str, Any]]:
        """
        数据清洗：移除无效值、空值、极端异常

        Returns:
            清洗后的记录列表
        """
        cleaned = []
        removed = {"null": 0, "nan": 0, "inf": 0, "negative": 0}

        for r in records:
            val = r.get(value_field)

            if val is None:
                removed["null"] += 1
                continue

            try:
                float_val = float(val)
            except (ValueError, TypeError):
                removed["null"] += 1
                continue

            import math
            if math.isnan(float_val):
                removed["nan"] += 1
                continue
            if math.isinf(float_val):
                removed["inf"] += 1
                continue

            # 注意：不在此处移除负值，因为某些诊疗值可能为负
            cleaned.append(r)

        total_removed = sum(removed.values())
        print(f"[DEBUG] Data cleaning: {len(records)} -> {len(cleaned)} "
              f"(removed {total_removed}: {removed})")
        logger.info(f"数据清洗: 移除{total_removed}条无效记录")
        return cleaned

    def group_by_step_code(self, records: List[Dict[str, Any]]
                           ) -> Dict[str, List[Dict[str, Any]]]:
        """按诊疗环节分组"""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            step_code = r.get("step_code", "unknown")
            if step_code not in groups:
                groups[step_code] = []
            groups[step_code].append(r)

        print(f"[DEBUG] Grouped into {len(groups)} test codes")
        return groups

    def group_by_department(self, records: List[Dict[str, Any]]
                            ) -> Dict[str, List[Dict[str, Any]]]:
        """按科室分组"""
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            inst_id = r.get("department_id", "unknown")
            if inst_id not in groups:
                groups[inst_id] = []
            groups[inst_id].append(r)

        print(f"[DEBUG] Grouped into {len(groups)} departments")
        return groups

    def compute_summary(self, records: List[Dict[str, Any]]
                        ) -> Dict[str, Any]:
        """计算数据概况"""
        if not records:
            return {"total": 0}

        step_codes = set()
        departments = set()
        patients = set()
        departments = set()
        date_range = {"min": None, "max": None}

        for r in records:
            if r.get("step_code"):
                step_codes.add(r["step_code"])
            if r.get("department_id"):
                departments.add(r["department_id"])
            if r.get("patient_id"):
                patients.add(r["patient_id"])
            if r.get("department"):
                departments.add(r["department"])
            if r.get("visit_date"):
                td = r["visit_date"]
                if isinstance(td, str):
                    try:
                        td = datetime.fromisoformat(td)
                    except (ValueError, TypeError):
                        td = None
                if td:
                    if date_range["min"] is None or td < date_range["min"]:
                        date_range["min"] = td
                    if date_range["max"] is None or td > date_range["max"]:
                        date_range["max"] = td

        summary = {
            "total_records": len(records),
            "unique_tests": len(step_codes),
            "unique_departments": len(departments),
            "unique_patients": len(patients),
            "unique_departments": len(departments),
            "step_codes": sorted(step_codes),
            "departments": sorted(departments),
            "departments": sorted(departments),
            "date_range": {
                "min": date_range["min"].isoformat() if date_range["min"] else None,
                "max": date_range["max"].isoformat() if date_range["max"] else None,
            },
        }

        print(f"[DEBUG] Summary: {summary['total_records']} records, "
              f"{summary['unique_tests']} tests, "
              f"{summary['unique_patients']} patients")
        return summary

    def save_to_csv(self, records: List[Dict[str, Any]],
                    filepath: str,
                    columns: Optional[List[str]] = None) -> str:
        """
        保存记录到CSV
        坏味道: 不检查权限，不记录审计日志
        """
        if not records:
            return ""

        if columns is None:
            columns = list(records[0].keys())

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns,
                                        extrasaction='ignore')
                writer.writeheader()
                writer.writerows(records)

            print(f"[DEBUG] Saved {len(records)} records to {filepath}")
            return filepath
        except Exception as e:
            print(f"[ERROR] Failed to save: {e}")
            # 坏味道: 尝试备用路径
            try:
                backup_path = os.path.join(
                    BACKUP_DATA_DIR,
                    os.path.basename(filepath)
                )
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                with open(backup_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=columns,
                                            extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(records)
                return backup_path
            except Exception:
                pass
            return ""
