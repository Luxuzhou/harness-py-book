package com.example.sqc.model.ck;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * ClickHouse检验结果宽表
 * <p>
 * 对应ClickHouse数据库中的bi_inspect_result表，存储所有检验仪器的原始检验结果数据。
 * 该表为宽表设计，包含样本信息、仪器信息、项目信息、结果信息、质控信息等多维度字段。
 * 每日数据量约50万~200万行，用于实时质控分析和历史数据回溯。
 * </p>
 *
 * @author sqc-team
 * @since 2024-01-10
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("bi_inspect_result")
public class BiInspectResult {

    // ====================== 主键 ======================

    /**
     * 主键ID（ClickHouse自增或UUID）
     */
    @Id
    @Column("id")
    private Long id;

    /**
     * 数据批次号，用于ETL追踪
     */
    @Column("batch_no")
    private String batchNo;

    // ====================== 样本基础信息 ======================

    /**
     * 样本条码号
     */
    @Column("sample_barcode")
    private String sampleBarcode;

    /**
     * 样本类型（1=血清, 2=全血, 3=尿液, 4=脑脊液, 5=其他体液）
     */
    @Column("sample_type")
    private Integer sampleType;

    /**
     * 样本类型名称
     */
    @Column("sample_type_name")
    private String sampleTypeName;

    /**
     * 患者ID
     */
    @Column("patient_id")
    private String patientId;

    /**
     * 患者姓名（脱敏存储）
     */
    @Column("patient_name")
    private String patientName;

    /**
     * 患者性别（0=未知, 1=男, 2=女）
     */
    @Column("patient_gender")
    private Integer patientGender;

    /**
     * 患者年龄
     */
    @Column("patient_age")
    private Integer patientAge;

    /**
     * 患者年龄单位（Y=岁, M=月, D=天）
     */
    @Column("patient_age_unit")
    private String patientAgeUnit;

    /**
     * 就诊类型（1=门诊, 2=住院, 3=急诊, 4=体检）
     */
    @Column("visit_type")
    private Integer visitType;

    /**
     * 就诊类型名称
     */
    @Column("visit_type_name")
    private String visitTypeName;

    /**
     * 科室编码
     */
    @Column("dept_code")
    private String deptCode;

    /**
     * 科室名称
     */
    @Column("dept_name")
    private String deptName;

    /**
     * 病区编码
     */
    @Column("ward_code")
    private String wardCode;

    /**
     * 病区名称
     */
    @Column("ward_name")
    private String wardName;

    /**
     * 床号
     */
    @Column("bed_no")
    private String bedNo;

    // ====================== 医嘱/申请信息 ======================

    /**
     * 申请单号
     */
    @Column("request_no")
    private String requestNo;

    /**
     * 医嘱号
     */
    @Column("order_no")
    private String orderNo;

    /**
     * 申请医生编码
     */
    @Column("doctor_code")
    private String doctorCode;

    /**
     * 申请医生姓名
     */
    @Column("doctor_name")
    private String doctorName;

    /**
     * 临床诊断
     */
    @Column("clinical_diagnosis")
    private String clinicalDiagnosis;

    /**
     * 申请时间
     */
    @Column("request_time")
    private LocalDateTime requestTime;

    // ====================== 实验室信息 ======================

    /**
     * 实验室编码
     */
    @Column("lab_code")
    private String labCode;

    /**
     * 实验室名称
     */
    @Column("lab_name")
    private String labName;

    /**
     * 检验组编码（如：血常规组、生化全套组）
     */
    @Column("group_code")
    private String groupCode;

    /**
     * 检验组名称
     */
    @Column("group_name")
    private String groupName;

    /**
     * 专业组编码（如：临床化学、临床血液学）
     */
    @Column("specialty_code")
    private String specialtyCode;

    /**
     * 专业组名称
     */
    @Column("specialty_name")
    private String specialtyName;

    // ====================== 仪器信息 ======================

    /**
     * 仪器编码
     */
    @Column("instrument_code")
    private String instrumentCode;

    /**
     * 仪器名称
     */
    @Column("instrument_name")
    private String instrumentName;

    /**
     * 仪器型号
     */
    @Column("instrument_model")
    private String instrumentModel;

    /**
     * 仪器厂商
     */
    @Column("instrument_vendor")
    private String instrumentVendor;

    /**
     * 仪器通道号
     */
    @Column("channel_no")
    private String channelNo;

    /**
     * 仪器测试编号
     */
    @Column("test_no")
    private String testNo;

    // ====================== 检验项目信息 ======================

    /**
     * 检验项目编码
     */
    @Column("item_code")
    private String itemCode;

    /**
     * 检验项目名称
     */
    @Column("item_name")
    private String itemName;

    /**
     * 检验项目英文缩写
     */
    @Column("item_abbr")
    private String itemAbbr;

    /**
     * 结果单位
     */
    @Column("result_unit")
    private String resultUnit;

    /**
     * 方法学编码
     */
    @Column("method_code")
    private String methodCode;

    /**
     * 方法学名称
     */
    @Column("method_name")
    private String methodName;

    /**
     * 试剂批号
     */
    @Column("reagent_lot_no")
    private String reagentLotNo;

    /**
     * 试剂有效期
     */
    @Column("reagent_expiry_date")
    private LocalDate reagentExpiryDate;

    /**
     * 校准品批号
     */
    @Column("calibrator_lot_no")
    private String calibratorLotNo;

    /**
     * 校准时间
     */
    @Column("calibration_time")
    private LocalDateTime calibrationTime;

    // ====================== 检验结果信息 ======================

    /**
     * 检验结果值（数值型）
     */
    @Column("result_value")
    private BigDecimal resultValue;

    /**
     * 检验结果（原始字符串，可能含非数值结果如"阳性"）
     */
    @Column("result_text")
    private String resultText;

    /**
     * 结果标志（H=偏高, L=偏低, N=正常, C=危急值, P=阳性, A=异常）
     */
    @Column("result_flag")
    private String resultFlag;

    /**
     * 参考范围下限
     */
    @Column("ref_range_low")
    private BigDecimal refRangeLow;

    /**
     * 参考范围上限
     */
    @Column("ref_range_high")
    private BigDecimal refRangeHigh;

    /**
     * 参考范围文本（如"3.5-5.0"或"阴性"）
     */
    @Column("ref_range_text")
    private String refRangeText;

    /**
     * 危急值下限
     */
    @Column("critical_low")
    private BigDecimal criticalLow;

    /**
     * 危急值上限
     */
    @Column("critical_high")
    private BigDecimal criticalHigh;

    /**
     * 是否为危急值（0=否, 1=是）
     */
    @Column("is_critical")
    private Integer isCritical;

    /**
     * 小数位数
     */
    @Column("decimal_places")
    private Integer decimalPlaces;

    // ====================== 质控相关信息 ======================

    /**
     * 是否为质控数据（0=患者样本, 1=质控样本）
     */
    @Column("is_qc_data")
    private Integer isQcData;

    /**
     * 质控品批号
     */
    @Column("control_lot_no")
    private String controlLotNo;

    /**
     * 质控品水平（1=低值, 2=正常值, 3=高值）
     */
    @Column("control_level")
    private Integer controlLevel;

    /**
     * 质控品水平名称
     */
    @Column("control_level_name")
    private String controlLevelName;

    /**
     * 质控品厂商
     */
    @Column("control_vendor")
    private String controlVendor;

    /**
     * 质控品名称
     */
    @Column("control_name")
    private String controlName;

    /**
     * 质控品有效期
     */
    @Column("control_expiry_date")
    private LocalDate controlExpiryDate;

    /**
     * 质控靶值
     */
    @Column("qc_target_value")
    private BigDecimal qcTargetValue;

    /**
     * 质控标准差
     */
    @Column("qc_target_sd")
    private BigDecimal qcTargetSd;

    /**
     * 质控变异系数
     */
    @Column("qc_target_cv")
    private BigDecimal qcTargetCv;

    /**
     * 质控规则判定结果（PASS=通过, WARN=警告, FAIL=失控）
     */
    @Column("qc_rule_result")
    private String qcRuleResult;

    /**
     * 触发的质控规则编码（如：1-3s, 2-2s, R-4s）
     */
    @Column("qc_rule_code")
    private String qcRuleCode;

    // ====================== 流程状态信息 ======================

    /**
     * 检验状态（0=待检, 1=检测中, 2=已出结果, 3=已审核, 4=已发布）
     */
    @Column("inspect_status")
    private Integer inspectStatus;

    /**
     * 检验状态名称
     */
    @Column("inspect_status_name")
    private String inspectStatusName;

    /**
     * 审核状态（0=未审核, 1=已审核, 2=已退回）
     */
    @Column("verify_status")
    private Integer verifyStatus;

    /**
     * 审核医师编码
     */
    @Column("verifier_code")
    private String verifierCode;

    /**
     * 审核医师姓名
     */
    @Column("verifier_name")
    private String verifierName;

    /**
     * 审核时间
     */
    @Column("verify_time")
    private LocalDateTime verifyTime;

    /**
     * 报告医师编码
     */
    @Column("reporter_code")
    private String reporterCode;

    /**
     * 报告医师姓名
     */
    @Column("reporter_name")
    private String reporterName;

    // ====================== 时间维度信息 ======================

    /**
     * 采样时间
     */
    @Column("collect_time")
    private LocalDateTime collectTime;

    /**
     * 接收时间
     */
    @Column("receive_time")
    private LocalDateTime receiveTime;

    /**
     * 上机时间
     */
    @Column("inspect_time")
    private LocalDateTime inspectTime;

    /**
     * 出结果时间
     */
    @Column("result_time")
    private LocalDateTime resultTime;

    /**
     * 报告时间
     */
    @Column("report_time")
    private LocalDateTime reportTime;

    /**
     * TAT（样本周转时间，单位：分钟）
     */
    @Column("tat_minutes")
    private Integer tatMinutes;

    /**
     * 检验日期（分区键）
     */
    @Column("inspect_date")
    private LocalDate inspectDate;

    // ====================== ETL与元数据 ======================

    /**
     * 数据来源系统编码（LIS/HIS/第三方）
     */
    @Column("source_system")
    private String sourceSystem;

    /**
     * 数据来源系统中的原始ID
     */
    @Column("source_id")
    private String sourceId;

    /**
     * 数据入库时间
     */
    @Column("etl_time")
    private LocalDateTime etlTime;

    /**
     * ETL处理批次号
     */
    @Column("etl_batch_no")
    private String etlBatchNo;

    /**
     * 数据质量标记（0=正常, 1=可疑, 2=无效）
     */
    @Column("data_quality_flag")
    private Integer dataQualityFlag;

    /**
     * 数据质量备注
     */
    @Column("data_quality_remark")
    private String dataQualityRemark;

    /**
     * 是否已删除（逻辑删除, 0=否, 1=是）
     */
    @Column("is_deleted")
    private Integer isDeleted;

    /**
     * 创建时间
     */
    @Column("create_time")
    private LocalDateTime createTime;

    /**
     * 更新时间
     */
    @Column("update_time")
    private LocalDateTime updateTime;

    /**
     * 备注
     */
    @Column("remark")
    private String remark;
}
