package com.example.cp.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 科室校准记录实体
 *
 * @author cp-team
 * @since 2024-02-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_calibration_record")
public class CpCalibrationRecord {

    @Id
    @Column("id")
    private String id;

    @Column("instrument_code")
    private String instrumentCode;

    @Column("instrument_name")
    private String instrumentName;

    @Column("item_code")
    private String itemCode;

    @Column("item_name")
    private String itemName;

    @Column("calibrator_lot_no")
    private String calibratorLotNo;

    @Column("calibrator_name")
    private String calibratorName;

    @Column("calibrator_level")
    private Integer calibratorLevel;

    @Column("target_value")
    private BigDecimal targetValue;

    @Column("measured_value")
    private BigDecimal measuredValue;

    @Column("deviation")
    private BigDecimal deviation;

    @Column("deviation_pct")
    private BigDecimal deviationPct;

    @Column("calibration_result")
    private String calibrationResult;

    @Column("calibration_time")
    private LocalDateTime calibrationTime;

    @Column("operator")
    private String operator;

    @Column("lab_code")
    private String labCode;

    @Column("remark")
    private String remark;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
