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
 * 诊疗环节实体
 *
 * @author cp-team
 * @since 2024-01-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_treatment_step")
public class CpTreatmentStep {

    @Id
    @Column("id")
    private String id;

    @Column("item_code")
    private String itemCode;

    @Column("item_name")
    private String itemName;

    @Column("item_abbr")
    private String itemAbbr;

    @Column("item_english_name")
    private String itemEnglishName;

    @Column("result_unit")
    private String resultUnit;

    @Column("decimal_places")
    private Integer decimalPlaces;

    @Column("ref_range_low")
    private BigDecimal refRangeLow;

    @Column("ref_range_high")
    private BigDecimal refRangeHigh;

    @Column("critical_low")
    private BigDecimal criticalLow;

    @Column("critical_high")
    private BigDecimal criticalHigh;

    @Column("method_code")
    private String methodCode;

    @Column("method_name")
    private String methodName;

    @Column("specialty_code")
    private String specialtyCode;

    @Column("specialty_name")
    private String specialtyName;

    @Column("lab_code")
    private String labCode;

    @Column("item_status")
    private Integer itemStatus;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("update_time")
    private LocalDateTime updateTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
