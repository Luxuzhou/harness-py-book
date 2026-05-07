"""
Pydantic数据模型定义

本模块是临床数据合规服务的核心数据契约层，参照真实生产系统脱敏改写。
包含 50+ 个模型，覆盖患者筛选、任务配置、检验结果、仪器管理等维度，
同时承载 PII 脱敏规则、字段级权限约束、审计追溯元数据。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
)


# ──────────────────────────────────────────────────────────────
# 枚举定义
# ──────────────────────────────────────────────────────────────
class GenderEnum(str, Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"
    OTHER = "other"


class SpecimenTypeEnum(str, Enum):
    SERUM = "serum"
    PLASMA = "plasma"
    WHOLE_BLOOD = "whole_blood"
    URINE = "urine"
    CSF = "csf"
    OTHER = "other"


class AnalyzerStatusEnum(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"
    CALIBRATING = "calibrating"
    ERROR = "error"


class QCStatusEnum(str, Enum):
    IN_CONTROL = "in_control"
    WARNING = "warning"
    OUT_OF_CONTROL = "out_of_control"
    NOT_EVALUATED = "not_evaluated"


class MAMethodEnum(str, Enum):
    MA = "MA"
    WMA = "WMA"
    EWMA = "EWMA"
    MP = "MP"


class TransformMethodEnum(str, Enum):
    AUTO = "auto"
    BOX_COX = "box-cox"
    LOG = "log"
    SQRT = "sqrt"
    YEO_JOHNSON = "yeo-johnson"
    NONE = "none"


class TruncationMethodEnum(str, Enum):
    IQR = "IQR"
    Z_SCORE = "Z-score"
    MODIFIED_Z = "Modified-Z"
    PERCENTILE = "Percentile"
    NONE = "none"


class ExportFormatEnum(str, Enum):
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    PDF = "pdf"


class FilterOperatorEnum(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    LIKE = "like"
    NOT_LIKE = "not_like"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class SortDirectionEnum(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TaskStatusEnum(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SeverityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditActionEnum(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"
    QUERY = "query"


class RegressionMethodEnum(str, Enum):
    OLS = "ols"
    DEMING = "deming"
    PASSING_BABLOK = "passing-bablok"


# ──────────────────────────────────────────────────────────────
# 基础模型
# ──────────────────────────────────────────────────────────────
class BaseResponse(BaseModel):
    """通用API响应基类"""
    success: bool = True
    message: str = ""
    code: int = 200
    timestamp: datetime = Field(default_factory=datetime.now)


class PaginationParams(BaseModel):
    """分页参数"""
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=1000, description="每页大小")
    total: Optional[int] = Field(default=None, description="总记录数")
    total_pages: Optional[int] = Field(default=None, description="总页数")


class SortParams(BaseModel):
    """排序参数"""
    field: str = Field(default="id", description="排序字段")
    direction: SortDirectionEnum = Field(
        default=SortDirectionEnum.ASC, description="排序方向"
    )


# ──────────────────────────────────────────────────────────────
# 患者模型
# ──────────────────────────────────────────────────────────────
class PatientBase(BaseModel):
    """患者基础信息"""
    patient_id: str = Field(..., description="患者ID", min_length=1)
    name: Optional[str] = Field(default=None, description="患者姓名")
    gender: Optional[GenderEnum] = Field(default=None, description="性别")
    age: Optional[Union[int, str]] = Field(default=None, description="年龄")
    id_card: Optional[str] = Field(default=None, description="身份证号")
    department: Optional[str] = Field(default=None, description="科室")
    diagnosis: Optional[str] = Field(default=None, description="诊断")
    admission_date: Optional[date] = Field(default=None, description="入院日期")
    bed_number: Optional[str] = Field(default=None, description="床号")
    physician: Optional[str] = Field(default=None, description="主治医生")
    contact_phone: Optional[str] = Field(default=None, description="联系电话")
    address: Optional[str] = Field(default=None, description="地址")
    insurance_type: Optional[str] = Field(default=None, description="医保类型")
    allergies: Optional[List[str]] = Field(default=None, description="过敏史")
    medications: Optional[List[str]] = Field(default=None, description="当前用药")


class PatientCreate(PatientBase):
    """创建患者"""
    pass


class PatientUpdate(BaseModel):
    """更新患者"""
    name: Optional[str] = None
    gender: Optional[GenderEnum] = None
    age: Optional[Union[int, str]] = None
    department: Optional[str] = None
    diagnosis: Optional[str] = None
    physician: Optional[str] = None
    medications: Optional[List[str]] = None


class PatientResponse(PatientBase):
    """患者响应（包含PII，坏味道：未脱敏）"""
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PatientListResponse(BaseResponse):
    """患者列表响应"""
    data: List[PatientResponse] = Field(default_factory=list)
    pagination: Optional[PaginationParams] = None


# ──────────────────────────────────────────────────────────────
# 诊疗记录模型
# ──────────────────────────────────────────────────────────────
class LabResultBase(BaseModel):
    """诊疗记录基础"""
    result_id: Optional[str] = Field(default=None, description="结果ID")
    patient_id: str = Field(..., description="患者ID")
    step_code: str = Field(..., description="诊疗代码")
    step_name: Optional[str] = Field(default=None, description="诊疗名称")
    value: Optional[float] = Field(default=None, description="诊疗值")
    value_text: Optional[str] = Field(default=None, description="文本结果")
    unit: Optional[str] = Field(default=None, description="单位")
    reference_low: Optional[float] = Field(default=None, description="参考范围下限")
    reference_high: Optional[float] = Field(default=None, description="参考范围上限")
    flag: Optional[str] = Field(default=None, description="标志(H/L/N)")
    department_id: Optional[str] = Field(default=None, description="科室ID")
    visit_date: Optional[datetime] = Field(default=None, description="诊疗日期")
    report_date: Optional[datetime] = Field(default=None, description="报告日期")
    specimen_type: Optional[SpecimenTypeEnum] = Field(
        default=None, description="标本类型"
    )
    specimen_id: Optional[str] = Field(default=None, description="标本ID")
    operator: Optional[str] = Field(default=None, description="操作员")
    verified_by: Optional[str] = Field(default=None, description="审核者")
    comment: Optional[str] = Field(default=None, description="备注")


class LabResultCreate(LabResultBase):
    """创建诊疗记录"""
    pass


class LabResultResponse(LabResultBase):
    """诊疗记录响应"""
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None
    is_abnormal: Optional[bool] = None

    @model_validator(mode="after")
    def compute_abnormal_flag(self) -> "LabResultResponse":
        """自动计算异常标志"""
        if (self.value is not None and
                self.reference_low is not None and
                self.reference_high is not None):
            self.is_abnormal = (
                self.value < self.reference_low or
                self.value > self.reference_high
            )
        return self


class LabResultListResponse(BaseResponse):
    """诊疗记录列表响应"""
    data: List[LabResultResponse] = Field(default_factory=list)
    pagination: Optional[PaginationParams] = None


class LabResultBatchCreate(BaseModel):
    """批量创建诊疗记录"""
    results: List[LabResultCreate] = Field(
        ..., min_length=1, max_length=10000,
        description="诊疗记录列表"
    )
    department_id: Optional[str] = None
    operator: Optional[str] = None


# ──────────────────────────────────────────────────────────────
# 科室模型
# ──────────────────────────────────────────────────────────────
class InstrumentBase(BaseModel):
    """科室基础信息"""
    department_id: str = Field(..., description="科室ID")
    name: str = Field(..., description="科室名称")
    manufacturer: Optional[str] = Field(default=None, description="厂商")
    model: Optional[str] = Field(default=None, description="型号")
    serial_number: Optional[str] = Field(default=None, description="序列号")
    department: Optional[str] = Field(default=None, description="所属科室")
    location: Optional[str] = Field(default=None, description="位置")
    status: AnalyzerStatusEnum = Field(
        default=AnalyzerStatusEnum.ONLINE, description="状态"
    )
    last_calibration: Optional[datetime] = Field(
        default=None, description="上次校准时间"
    )
    next_calibration: Optional[datetime] = Field(
        default=None, description="下次校准时间"
    )
    supported_tests: List[str] = Field(
        default_factory=list, description="支持的诊疗环节"
    )
    daily_capacity: Optional[int] = Field(
        default=None, description="日处理能力"
    )


class InstrumentResponse(InstrumentBase):
    """科室响应"""
    model_config = ConfigDict(from_attributes=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    current_qc_status: QCStatusEnum = Field(
        default=QCStatusEnum.NOT_EVALUATED
    )


class InstrumentListResponse(BaseResponse):
    """科室列表响应"""
    data: List[InstrumentResponse] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# 过滤模型：支持嵌套的多维度条件组合与布尔表达式
# ──────────────────────────────────────────────────────────────
class FilterItem(BaseModel):
    """单个过滤条件"""
    field: str = Field(..., description="过滤字段")
    operator: FilterOperatorEnum = Field(
        default=FilterOperatorEnum.EQ, description="操作符"
    )
    value: Any = Field(default=None, description="过滤值")
    values: Optional[List[Any]] = Field(
        default=None, description="多值（用于IN/NOT_IN）"
    )
    case_sensitive: bool = Field(default=True, description="大小写敏感")

    @field_validator("value", mode="before")
    @classmethod
    def coerce_bool_from_list(cls, v: Any) -> Any:
        """
        坏味道: 复杂的类型强制转换
        将列表中的单个值转换为标量
        """
        if isinstance(v, list):
            if len(v) == 1:
                return v[0]
            elif len(v) == 0:
                return None
        if isinstance(v, str):
            if v.lower() in ("true", "1", "yes", "是"):
                return True
            if v.lower() in ("false", "0", "no", "否"):
                return False
        return v


class FilterGroup(BaseModel):
    """过滤条件组（AND/OR逻辑）"""
    logic: str = Field(default="AND", pattern="^(AND|OR)$", description="逻辑运算符")
    filters: List[Union[FilterItem, "FilterGroup"]] = Field(
        default_factory=list, description="过滤条件列表"
    )

    def to_flat_conditions(self) -> List[Dict[str, Any]]:
        """展平为条件列表（递归）"""
        conditions = []
        for f in self.filters:
            if isinstance(f, FilterItem):
                conditions.append({
                    "field": f.field,
                    "operator": f.operator.value,
                    "value": f.value,
                    "values": f.values,
                })
            elif isinstance(f, FilterGroup):
                sub = f.to_flat_conditions()
                conditions.append({
                    "logic": f.logic,
                    "conditions": sub,
                })
        return conditions


# ──────────────────────────────────────────────────────────────
# 患者筛选条件：支持按疾病、时段、科室、年龄、性别多维度过滤
# ──────────────────────────────────────────────────────────────
class DepartmentFilter(BaseModel):
    """科室过滤"""
    include: List[str] = Field(default_factory=list, description="包含的科室")
    exclude: List[str] = Field(default_factory=list, description="排除的科室")


class AgeFilter(BaseModel):
    """年龄过滤"""
    min_age: Optional[int] = Field(default=None, ge=0, le=150, description="最小年龄")
    max_age: Optional[int] = Field(default=None, ge=0, le=150, description="最大年龄")

    @model_validator(mode="after")
    def validate_range(self) -> "AgeFilter":
        if (self.min_age is not None and self.max_age is not None
                and self.min_age > self.max_age):
            raise ValueError("min_age不能大于max_age")
        return self


class DiagnosisFilter(BaseModel):
    """诊断过滤"""
    include_keywords: List[str] = Field(
        default_factory=list, description="包含的诊断关键词"
    )
    exclude_keywords: List[str] = Field(
        default_factory=list, description="排除的诊断关键词"
    )
    icd_codes: List[str] = Field(
        default_factory=list, description="ICD诊断编码"
    )


class MedicationFilter(BaseModel):
    """用药过滤"""
    exclude_medications: List[str] = Field(
        default_factory=list, description="排除的药物"
    )
    include_medications: List[str] = Field(
        default_factory=list, description="仅包含使用这些药物的患者"
    )


class SpecimenFilter(BaseModel):
    """标本特性过滤"""
    specimen_types: List[SpecimenTypeEnum] = Field(
        default_factory=list, description="标本类型"
    )
    exclude_hemolysis: bool = Field(default=False, description="排除溶血标本")
    exclude_lipemia: bool = Field(default=False, description="排除脂血标本")
    exclude_icterus: bool = Field(default=False, description="排除黄疸标本")
    min_volume_ml: Optional[float] = Field(default=None, description="最小标本量(ml)")


class TimeRangeFilter(BaseModel):
    """时间范围过滤"""
    start_date: Optional[datetime] = Field(default=None, description="开始时间")
    end_date: Optional[datetime] = Field(default=None, description="结束时间")
    recent_days: Optional[int] = Field(
        default=None, ge=1, description="最近N天"
    )
    time_slots: Optional[List[str]] = Field(
        default=None, description="时间段(如'08:00-12:00')"
    )


class SimulationFilters(BaseModel):
    """
    综合模拟过滤条件。

    聚合性别、年龄、科室、检验类型、时段等多维度筛选器，
    用于临床路径分析任务的入参约束。
    """
    gender: Optional[GenderEnum] = Field(default=None, description="性别过滤")
    age: Optional[AgeFilter] = Field(default=None, description="年龄过滤")
    department: Optional[DepartmentFilter] = Field(
        default=None, description="科室过滤"
    )
    diagnosis: Optional[DiagnosisFilter] = Field(
        default=None, description="诊断过滤"
    )
    medication: Optional[MedicationFilter] = Field(
        default=None, description="用药过滤"
    )
    specimen: Optional[SpecimenFilter] = Field(
        default=None, description="标本过滤"
    )
    time_range: Optional[TimeRangeFilter] = Field(
        default=None, description="时间范围"
    )
    custom_filters: Optional[FilterGroup] = Field(
        default=None, description="自定义过滤条件组"
    )
    exclude_repeat_patients: bool = Field(
        default=False, description="排除重复患者"
    )
    min_result_count: Optional[int] = Field(
        default=None, ge=1, description="患者最少结果数"
    )

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, v: Any) -> Any:
        """标准化性别值"""
        if v is None:
            return None
        if isinstance(v, str):
            mapping = {
                "男": GenderEnum.MALE, "M": GenderEnum.MALE,
                "male": GenderEnum.MALE, "男性": GenderEnum.MALE,
                "女": GenderEnum.FEMALE, "F": GenderEnum.FEMALE,
                "female": GenderEnum.FEMALE, "女性": GenderEnum.FEMALE,
            }
            return mapping.get(v, v)
        return v


# ──────────────────────────────────────────────────────────────
# PathwayAnalytics配置模型
# ──────────────────────────────────────────────────────────────
class DataConfig(BaseModel):
    """数据源配置"""
    source_type: str = Field(
        default="database", description="数据源类型(database/csv/api)"
    )
    connection_string: Optional[str] = Field(
        default=None, description="数据库连接字符串"
    )
    table_name: Optional[str] = Field(default=None, description="表名")
    csv_path: Optional[str] = Field(default=None, description="CSV文件路径")
    api_url: Optional[str] = Field(default=None, description="API地址")
    cache_enabled: bool = Field(default=True, description="启用缓存")
    cache_ttl_seconds: int = Field(default=300, description="缓存过期时间")


class Objectives(BaseModel):
    """分析目标配置"""
    target_cv: Optional[float] = Field(
        default=None, ge=0, le=100, description="目标CV%"
    )
    target_mean: Optional[float] = Field(default=None, description="目标均值")
    target_bias: Optional[float] = Field(
        default=None, description="目标偏倚(%)"
    )
    sigma_level: Optional[float] = Field(
        default=None, ge=2, le=6, description="目标Sigma水平"
    )
    tea: Optional[float] = Field(
        default=None, ge=0, description="总允许误差(%)"
    )
    allowable_imprecision: Optional[float] = Field(
        default=None, ge=0, description="允许不精密度(%)"
    )
    allowable_bias: Optional[float] = Field(
        default=None, ge=0, description="允许偏倚(%)"
    )


class QCRuleConfig(BaseModel):
    """临床路径规则配置"""
    rule_1_2s: bool = Field(default=True, description="启用1-2s规则")
    rule_1_3s: bool = Field(default=True, description="启用1-3s规则")
    rule_2_2s: bool = Field(default=True, description="启用2-2s规则")
    rule_r_4s: bool = Field(default=True, description="启用R-4s规则")
    rule_4_1s: bool = Field(default=False, description="启用4-1s规则")
    rule_10_x: bool = Field(default=False, description="启用10-x规则")
    custom_sigma: float = Field(
        default=3.0, ge=1.0, le=6.0, description="控制限倍数"
    )


class MAConfig(BaseModel):
    """路径依从率配置"""
    method: MAMethodEnum = Field(
        default=MAMethodEnum.EWMA, description="路径依从率方法"
    )
    window_size: int = Field(
        default=20, ge=5, le=500, description="窗口大小"
    )
    alpha: float = Field(
        default=0.2, ge=0.01, le=1.0, description="EWMA平滑系数"
    )
    warm_up_size: int = Field(
        default=50, ge=10, description="预热数据量"
    )


class TransformConfig(BaseModel):
    """数据变换配置"""
    method: TransformMethodEnum = Field(
        default=TransformMethodEnum.AUTO, description="变换方法"
    )
    test_normality: bool = Field(
        default=True, description="是否诊疗正态性"
    )
    alpha: float = Field(
        default=0.05, ge=0.001, le=0.1, description="显著性水平"
    )


class TruncationConfig(BaseModel):
    """截断配置"""
    method: TruncationMethodEnum = Field(
        default=TruncationMethodEnum.IQR, description="截断方法"
    )
    factor: float = Field(
        default=1.5, ge=0.5, le=5.0, description="截断系数"
    )
    percentile_lower: float = Field(
        default=2.5, ge=0, le=50, description="下百分位数"
    )
    percentile_upper: float = Field(
        default=97.5, ge=50, le=100, description="上百分位数"
    )


class TaskConfig(BaseModel):
    """
    分析任务完整配置。

    覆盖任务元信息、输入参数、输出选项、调度策略四组字段，
    被 pathway_analyzer、anomaly_rule_engine、export 三条主链共用。
    """
    task_id: Optional[str] = Field(default=None, description="任务ID")
    task_name: Optional[str] = Field(default=None, description="任务名称")
    step_code: str = Field(..., description="诊疗环节代码")
    step_name: Optional[str] = Field(default=None, description="诊疗环节名称")
    department_id: Optional[str] = Field(default=None, description="科室ID")
    department_ids: List[str] = Field(
        default_factory=list, description="多科室ID列表"
    )

    # 子配置
    data_config: DataConfig = Field(
        default_factory=DataConfig, description="数据源配置"
    )
    objectives: Objectives = Field(
        default_factory=Objectives, description="分析目标"
    )
    filters: SimulationFilters = Field(
        default_factory=SimulationFilters, description="过滤条件"
    )
    qc_rules: QCRuleConfig = Field(
        default_factory=QCRuleConfig, description="临床路径规则"
    )
    ma_config: MAConfig = Field(
        default_factory=MAConfig, description="路径依从率配置"
    )
    transform_config: TransformConfig = Field(
        default_factory=TransformConfig, description="变换配置"
    )
    truncation_config: TruncationConfig = Field(
        default_factory=TruncationConfig, description="截断配置"
    )

    # 运行参数
    min_data_points: int = Field(
        default=50, ge=10, description="最小数据量"
    )
    max_data_points: Optional[int] = Field(
        default=None, description="最大数据量"
    )
    auto_refresh: bool = Field(
        default=False, description="自动刷新"
    )
    refresh_interval_seconds: int = Field(
        default=300, ge=30, description="刷新间隔"
    )

    # 元数据
    created_by: Optional[str] = Field(default=None, description="创建者")
    created_at: Optional[datetime] = Field(default=None, description="创建时间")
    status: TaskStatusEnum = Field(
        default=TaskStatusEnum.PENDING, description="任务状态"
    )


class TaskConfigCreate(BaseModel):
    """创建任务配置请求"""
    step_code: str = Field(..., description="诊疗环节代码")
    step_name: Optional[str] = None
    department_id: Optional[str] = None
    filters: Optional[SimulationFilters] = None
    qc_rules: Optional[QCRuleConfig] = None
    ma_config: Optional[MAConfig] = None
    transform_config: Optional[TransformConfig] = None
    truncation_config: Optional[TruncationConfig] = None
    min_data_points: int = Field(default=50, ge=10)


class TaskConfigResponse(BaseResponse):
    """任务配置响应"""
    data: Optional[TaskConfig] = None


class TaskConfigListResponse(BaseResponse):
    """任务配置列表响应"""
    data: List[TaskConfig] = Field(default_factory=list)
    pagination: Optional[PaginationParams] = None


# ──────────────────────────────────────────────────────────────
# 分析结果模型
# ──────────────────────────────────────────────────────────────
class StatisticsResult(BaseModel):
    """统计结果"""
    mean: float = 0.0
    median: float = 0.0
    std_dev: float = 0.0
    cv: float = 0.0
    skewness: float = 0.0
    kurtosis: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    count: int = 0
    q1: float = 0.0
    q3: float = 0.0
    iqr: float = 0.0
    is_normal: bool = False
    shapiro_p: float = 0.0


class RobustStatisticsResult(BaseModel):
    """稳健统计结果"""
    median: float = 0.0
    mad: float = 0.0
    mad_std: float = 0.0
    huber_mean: float = 0.0
    trimmed_mean_10: float = 0.0
    winsorized_mean_5: float = 0.0
    biweight_midvariance: float = 0.0


class TransformResultSchema(BaseModel):
    """变换结果"""
    method: str = ""
    lambda_param: Optional[float] = None
    is_normal_after: bool = False
    improvement: float = 0.0


class ControlLimits(BaseModel):
    """控制限"""
    center: float = 0.0
    ucl: float = 0.0
    lcl: float = 0.0
    uwl: float = 0.0
    lwl: float = 0.0


class MovingAverageResultSchema(BaseModel):
    """路径依从率结果"""
    method: str = ""
    window_size: int = 0
    data_points: int = 0
    control_limits: ControlLimits = Field(default_factory=ControlLimits)
    violation_count: int = 0


class WestgardViolation(BaseModel):
    """Westgard违规详情"""
    rule: str = ""
    violation_type: str = ""
    value: float = 0.0
    severity: str = ""
    patient_id: str = ""  # 坏味道: 包含PII
    description: str = ""


class WestgardResult(BaseModel):
    """Westgard规则检查结果"""
    total_violations: int = 0
    violations_by_rule: Dict[str, int] = Field(default_factory=dict)
    details: List[WestgardViolation] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """完整分析结果"""
    status: str = ""
    step_code: str = ""
    department_id: str = ""
    analysis_time: Optional[str] = None
    duration_seconds: float = 0.0
    data_summary: Dict[str, int] = Field(default_factory=dict)
    statistics: StatisticsResult = Field(default_factory=StatisticsResult)
    robust_statistics: RobustStatisticsResult = Field(
        default_factory=RobustStatisticsResult
    )
    transform: TransformResultSchema = Field(
        default_factory=TransformResultSchema
    )
    moving_average: MovingAverageResultSchema = Field(
        default_factory=MovingAverageResultSchema
    )
    westgard: WestgardResult = Field(default_factory=WestgardResult)


class AnalysisResultResponse(BaseResponse):
    """分析结果API响应"""
    data: Optional[AnalysisResult] = None


class BatchAnalysisResponse(BaseResponse):
    """批量分析响应"""
    data: Dict[str, AnalysisResult] = Field(default_factory=dict)
    total_tests: int = 0
    completed: int = 0
    failed: int = 0


# ──────────────────────────────────────────────────────────────
# 查询模型
# ──────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    """数据查询请求"""
    step_codes: List[str] = Field(
        default_factory=list, description="诊疗环节代码列表"
    )
    department_ids: List[str] = Field(
        default_factory=list, description="科室ID列表"
    )
    filters: Optional[SimulationFilters] = Field(
        default=None, description="过滤条件"
    )
    time_range: Optional[TimeRangeFilter] = Field(
        default=None, description="时间范围"
    )
    pagination: Optional[PaginationParams] = Field(
        default=None, description="分页参数"
    )
    sort: Optional[SortParams] = Field(
        default=None, description="排序参数"
    )
    include_patient_info: bool = Field(
        default=False, description="是否包含患者信息"
    )
    include_raw_values: bool = Field(
        default=True, description="是否包含原始值"
    )


class QueryResponse(BaseResponse):
    """数据查询响应"""
    data: List[Dict[str, Any]] = Field(default_factory=list)
    pagination: Optional[PaginationParams] = None
    query_time_ms: float = 0.0
    total_count: int = 0


# ──────────────────────────────────────────────────────────────
# 导出模型
# ──────────────────────────────────────────────────────────────
class ExportRequest(BaseModel):
    """数据导出请求"""
    format: ExportFormatEnum = Field(
        default=ExportFormatEnum.CSV, description="导出格式"
    )
    step_codes: List[str] = Field(
        default_factory=list, description="诊疗环节"
    )
    department_ids: List[str] = Field(
        default_factory=list, description="科室ID"
    )
    filters: Optional[SimulationFilters] = None
    time_range: Optional[TimeRangeFilter] = None
    include_patient_info: bool = Field(
        default=True, description="包含患者信息"
    )
    include_statistics: bool = Field(
        default=False, description="包含统计信息"
    )
    columns: Optional[List[str]] = Field(
        default=None, description="指定导出列"
    )
    # 坏味道: 不检查权限
    max_rows: int = Field(
        default=100000, ge=1, description="最大导出行数"
    )


class ExportResponse(BaseResponse):
    """导出响应"""
    download_url: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    row_count: int = 0
    format: str = ""


# ──────────────────────────────────────────────────────────────
# 参考范围模型
# ──────────────────────────────────────────────────────────────
class ReferenceRange(BaseModel):
    """参考范围"""
    step_code: str = Field(..., description="诊疗代码")
    step_name: str = Field(default="", description="诊疗名称")
    unit: str = Field(default="", description="单位")
    lower_limit: Optional[float] = Field(default=None, description="下限")
    upper_limit: Optional[float] = Field(default=None, description="上限")
    gender: Optional[GenderEnum] = Field(
        default=None, description="适用性别"
    )
    age_min: Optional[int] = Field(default=None, description="适用最小年龄")
    age_max: Optional[int] = Field(default=None, description="适用最大年龄")
    specimen_type: Optional[SpecimenTypeEnum] = Field(
        default=None, description="适用标本类型"
    )
    method: Optional[str] = Field(default=None, description="检测方法")
    source: Optional[str] = Field(
        default=None, description="参考范围来源"
    )


class ReferenceRangeListResponse(BaseResponse):
    """参考范围列表响应"""
    data: List[ReferenceRange] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────
# 回归归一化模型
# ──────────────────────────────────────────────────────────────
class NormalizationRequest(BaseModel):
    """归一化请求"""
    source_department_id: str = Field(..., description="源科室ID")
    target_department_id: str = Field(..., description="目标科室ID")
    step_code: str = Field(..., description="诊疗环节代码")
    method: RegressionMethodEnum = Field(
        default=RegressionMethodEnum.DEMING, description="回归方法"
    )
    time_range: Optional[TimeRangeFilter] = None
    min_pairs: int = Field(default=40, ge=10, description="最小配对数")


class NormalizationResult(BaseModel):
    """归一化结果"""
    method: str = ""
    slope: float = 0.0
    intercept: float = 0.0
    correlation: float = 0.0
    bias: float = 0.0
    bias_percent: float = 0.0
    rmse: float = 0.0
    sample_count: int = 0


class NormalizationResponse(BaseResponse):
    """归一化响应"""
    data: Optional[NormalizationResult] = None


# ──────────────────────────────────────────────────────────────
# 审计日志模型
# ──────────────────────────────────────────────────────────────
class AuditLogEntry(BaseModel):
    """审计日志条目"""
    id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = None
    action: AuditActionEnum = Field(
        default=AuditActionEnum.READ, description="操作类型"
    )
    resource_type: str = Field(default="", description="资源类型")
    resource_id: Optional[str] = Field(default=None, description="资源ID")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="详情"
    )
    ip_address: Optional[str] = Field(default=None, description="IP地址")
    user_agent: Optional[str] = Field(default=None, description="User-Agent")
    success: bool = Field(default=True, description="是否成功")


class AuditLogResponse(BaseResponse):
    """审计日志响应"""
    data: List[AuditLogEntry] = Field(default_factory=list)
    pagination: Optional[PaginationParams] = None


# ──────────────────────────────────────────────────────────────
# 趋势分析模型
# ──────────────────────────────────────────────────────────────
class TrendAnalysisRequest(BaseModel):
    """趋势分析请求"""
    step_code: str = Field(..., description="诊疗环节代码")
    department_id: Optional[str] = None
    time_range: Optional[TimeRangeFilter] = None
    ma_method: MAMethodEnum = Field(default=MAMethodEnum.EWMA)
    window_size: int = Field(default=20, ge=5)


class TrendAnalysisResult(BaseModel):
    """趋势分析结果"""
    trend_direction: str = ""
    slope: float = 0.0
    intercept: float = 0.0
    r_squared: float = 0.0
    p_value: float = 0.0
    cusum_max_pos: float = 0.0
    cusum_max_neg: float = 0.0
    change_points: List[Dict[str, Any]] = Field(default_factory=list)


class TrendAnalysisResponse(BaseResponse):
    """趋势分析响应"""
    data: Optional[TrendAnalysisResult] = None


# ──────────────────────────────────────────────────────────────
# 科室比较模型
# ──────────────────────────────────────────────────────────────
class InstrumentComparisonRequest(BaseModel):
    """科室比较请求"""
    department_id_1: str = Field(..., description="科室1 ID")
    department_id_2: str = Field(..., description="科室2 ID")
    step_code: str = Field(..., description="诊疗环节代码")
    time_range: Optional[TimeRangeFilter] = None
    regression_method: RegressionMethodEnum = Field(
        default=RegressionMethodEnum.DEMING
    )


class InstrumentComparisonResult(BaseModel):
    """科室比较结果"""
    department_id_1: str = ""
    department_id_2: str = ""
    step_code: str = ""
    slope: float = 0.0
    intercept: float = 0.0
    correlation: float = 0.0
    bias: float = 0.0
    bias_percent: float = 0.0
    t_test_p: float = 0.0
    f_test_p: float = 0.0
    significant_difference: bool = False
    sample_count: int = 0


class InstrumentComparisonResponse(BaseResponse):
    """科室比较响应"""
    data: Optional[InstrumentComparisonResult] = None


# ──────────────────────────────────────────────────────────────
# 数据质量模型
# ──────────────────────────────────────────────────────────────
class DataQualityScore(BaseModel):
    """数据质量评分"""
    overall_score: float = Field(default=0.0, ge=0, le=100)
    completeness: float = Field(default=0.0, ge=0, le=100)
    outlier_score: float = Field(default=0.0, ge=0, le=100)
    normality_score: float = Field(default=0.0, ge=0, le=100)
    precision_score: float = Field(default=0.0, ge=0, le=100)
    total_count: int = 0
    valid_count: int = 0
    outlier_count: int = 0


class DataQualityResponse(BaseResponse):
    """数据质量响应"""
    data: Optional[DataQualityScore] = None


# ──────────────────────────────────────────────────────────────
# 健康检查模型
# ──────────────────────────────────────────────────────────────
class HealthCheck(BaseModel):
    """健康检查"""
    status: str = "ok"
    version: str = ""
    uptime_seconds: float = 0.0
    database_connected: bool = False
    department_count: int = 0
    active_tasks: int = 0


class HealthCheckResponse(BaseResponse):
    """健康检查响应"""
    data: Optional[HealthCheck] = None


# ──────────────────────────────────────────────────────────────
# 路径变异智能预警模型
# ──────────────────────────────────────────────────────────────

class DeviationPoint(BaseModel):
    """超限点位信息"""
    model_config = ConfigDict(from_attributes=True)

    index: int = Field(..., description="超限点在序列中的位置索引")
    moving_average: float = Field(..., description="该点的路径依从率")
    upper_limit: float = Field(..., description="上控制限")
    lower_limit: float = Field(..., description="下控制限")
    direction: str = Field(..., description="超限方向: HIGH 或 LOW")


class AnomalyRuleResponse(BaseModel):
    """预警规则响应（对应 Java 端 AnomalyRuleResponse）"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="规则ID")
    test_item_id: str = Field(..., description="诊疗项目ID")
    test_item_name: str = Field(..., description="诊疗项目名称")
    window_size: int = Field(..., description="路径依从率窗口大小")
    consecutive_count: int = Field(..., description="连续超限判定次数")
    threshold_multiplier: float = Field(..., description="控制限倍数(相对SD)")
    target_value: float = Field(..., description="目标值(靶值)")
    sd_value: float = Field(..., description="标准差")
    enabled: bool = Field(..., description="是否启用")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class AnomalyEventCreateRequest(BaseModel):
    """异常事件创建请求（对应 Java 端 AnomalyEventCreateRequest）"""
    model_config = ConfigDict(from_attributes=True)

    rule_id: int = Field(..., description="关联的预警规则ID")
    test_item_id: str = Field(..., max_length=64, description="诊疗项目ID")
    triggered_at: str = Field(..., description="异常预警触发时间")
    severity: str = Field(..., description="严重程度: WARNING/CRITICAL")
    moving_averages: Optional[List[float]] = Field(None, description="触发时的路径依从率序列")
    deviation_points: Optional[List[DeviationPoint]] = Field(None, description="超限点位信息")
    message: Optional[str] = Field(None, max_length=512, description="异常预警描述信息")


class AnomalyEventResponse(BaseModel):
    """异常事件响应（对应 Java 端 AnomalyEventResponse）"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="事件ID")
    rule_id: int = Field(..., description="关联的预警规则ID")
    test_item_id: str = Field(..., description="诊疗项目ID")
    triggered_at: str = Field(..., description="异常预警触发时间")
    severity: str = Field(..., description="严重程度")
    message: Optional[str] = Field(None, description="异常预警描述信息")
    created_at: Optional[str] = Field(None, description="创建时间")


class AnomalyResult(BaseModel):
    """实时分析结果"""
    model_config = ConfigDict(from_attributes=True)

    test_item_id: str = Field(..., description="诊疗项目ID")
    triggered: bool = Field(..., description="是否触发异常预警")
    moving_averages: List[float] = Field(..., description="路径依从率序列")
    deviation_points: List[DeviationPoint] = Field(default_factory=list, description="超限点位列表")
    consecutive_count: int = Field(0, description="连续超限次数")
    severity: Optional[str] = Field(None, description="严重程度")
    event_id: Optional[int] = Field(None, description="异常事件ID（如果触发）")
    message: Optional[str] = Field(None, description="分析描述信息")


class AnomalySegment(BaseModel):
    """异常预警区段"""
    model_config = ConfigDict(from_attributes=True)

    start_index: int = Field(..., description="区段起始索引")
    end_index: int = Field(..., description="区段结束索引")
    deviation_count: int = Field(..., description="区段内超限点数")
    max_deviation: float = Field(..., description="最大偏离值")
    severity: str = Field(..., description="区段严重程度")


class HistoryAnalysis(BaseModel):
    """历史分析结果"""
    model_config = ConfigDict(from_attributes=True)

    test_item_id: str = Field(..., description="诊疗项目ID")
    start_date: str = Field(..., description="分析起始日期")
    end_date: str = Field(..., description="分析结束日期")
    data_points: int = Field(..., description="数据点数")
    moving_averages: List[float] = Field(..., description="路径依从率序列")
    deviation_points: List[DeviationPoint] = Field(default_factory=list, description="超限点位列表")
    segments: List[AnomalySegment] = Field(default_factory=list, description="异常预警区段列表")
    summary: Dict[str, Any] = Field(default_factory=dict, description="统计摘要")


class ErrorResponse(BaseModel):
    """错误响应（对应契约 ErrorResponse schema）"""
    error_code: str = Field(..., description="错误码")
    message: str = Field(..., description="错误描述")
    timestamp: Optional[str] = Field(None, description="错误发生时间")
