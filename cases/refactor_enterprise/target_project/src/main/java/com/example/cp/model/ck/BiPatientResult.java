package com.example.cp.model.ck;

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
 * ClickHouse患者诊疗结果表（用于患者数据均值分析）
 * <p>
 * 与bi_inspect_result结构类似，但只存储患者样本数据（非临床路径样本），
 * 用于基于患者数据的路径依从率（PBRTQC）分析。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-01
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("bi_patient_result")
public class BiPatientRecord {

    @Id
    @Column("id")
    private Long id;

    @Column("sample_barcode")
    private String sampleBarcode;

    @Column("sample_type")
    private Integer sampleType;

    @Column("patient_id")
    private String patientId;

    @Column("patient_gender")
    private Integer patientGender;

    @Column("patient_age")
    private Integer patientAge;

    @Column("patient_age_unit")
    private String patientAgeUnit;

    @Column("visit_type")
    private Integer visitType;

    @Column("dept_code")
    private String deptCode;

    @Column("dept_name")
    private String deptName;

    @Column("lab_code")
    private String labCode;

    @Column("instrument_code")
    private String instrumentCode;

    @Column("instrument_name")
    private String instrumentName;

    @Column("item_code")
    private String itemCode;

    @Column("item_name")
    private String itemName;

    @Column("result_value")
    private BigDecimal resultValue;

    @Column("result_text")
    private String resultText;

    @Column("result_flag")
    private String resultFlag;

    @Column("result_unit")
    private String resultUnit;

    @Column("method_code")
    private String methodCode;

    @Column("ref_range_low")
    private BigDecimal refRangeLow;

    @Column("ref_range_high")
    private BigDecimal refRangeHigh;

    @Column("reagent_lot_no")
    private String reagentLotNo;

    @Column("calibrator_lot_no")
    private String calibratorLotNo;

    @Column("inspect_time")
    private LocalDateTime inspectTime;

    @Column("inspect_date")
    private LocalDate inspectDate;

    @Column("verify_status")
    private Integer verifyStatus;

    @Column("source_system")
    private String sourceSystem;

    @Column("etl_time")
    private LocalDateTime etlTime;

    @Column("data_quality_flag")
    private Integer dataQualityFlag;

    @Column("is_deleted")
    private Integer isDeleted;

    @Column("create_time")
    private LocalDateTime createTime;
}
