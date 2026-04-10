package com.example.sqc.model;

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
 * 仪器比对结果实体
 * <p>
 * 存储两台仪器间的比对分析结果，包括回归参数、偏倚、相关系数等。
 * </p>
 *
 * @author sqc-team
 * @since 2024-02-25
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("sqc_comparison_result")
public class SqcComparisonResult {

    @Id
    @Column("id")
    private String id;

    /** 实验室编码 */
    @Column("lab_code")
    private String labCode;

    /** 主仪器编码 */
    @Column("primary_instrument_code")
    private String primaryInstrumentCode;

    /** 主仪器名称 */
    @Column("primary_instrument_name")
    private String primaryInstrumentName;

    /** 比对仪器编码 */
    @Column("secondary_instrument_code")
    private String secondaryInstrumentCode;

    /** 比对仪器名称 */
    @Column("secondary_instrument_name")
    private String secondaryInstrumentName;

    /** 检验项目编码 */
    @Column("item_code")
    private String itemCode;

    /** 检验项目名称 */
    @Column("item_name")
    private String itemName;

    /** 比对方法（PASSING_BABLOK/DEMING/BLAND_ALTMAN/LINEAR_REGRESSION） */
    @Column("comparison_method")
    private String comparisonMethod;

    /** 数据对数 */
    @Column("data_pair_count")
    private Integer dataPairCount;

    /** 斜率 */
    @Column("slope")
    private BigDecimal slope;

    /** 截距 */
    @Column("intercept")
    private BigDecimal intercept;

    /** 相关系数R */
    @Column("correlation_r")
    private BigDecimal correlationR;

    /** R平方 */
    @Column("r_squared")
    private BigDecimal rSquared;

    /** 平均偏倚(%) */
    @Column("mean_bias")
    private BigDecimal meanBias;

    /** 平均偏倚绝对值 */
    @Column("mean_bias_abs")
    private BigDecimal meanBiasAbs;

    /** 偏倚标准差 */
    @Column("bias_sd")
    private BigDecimal biasSd;

    /** 95%一致性上限 */
    @Column("loa_upper")
    private BigDecimal loaUpper;

    /** 95%一致性下限 */
    @Column("loa_lower")
    private BigDecimal loaLower;

    /** 可接受偏倚标准(%) */
    @Column("acceptable_bias")
    private BigDecimal acceptableBias;

    /** 可接受CV标准(%) */
    @Column("acceptable_cv")
    private BigDecimal acceptableCv;

    /** 评估结果（PASS/FAIL/CONDITIONAL） */
    @Column("evaluation_result")
    private String evaluationResult;

    /** 评估评语 */
    @Column("evaluation_comment")
    private String evaluationComment;

    /** 比对日期范围-开始 */
    @Column("start_date")
    private LocalDate startDate;

    /** 比对日期范围-结束 */
    @Column("end_date")
    private LocalDate endDate;

    /** 创建人 */
    @Column("creator")
    private String creator;

    /** 创建时间 */
    @Column("create_time")
    private LocalDateTime createTime;

    /** 更新时间 */
    @Column("update_time")
    private LocalDateTime updateTime;

    /** 是否删除 */
    @Column("is_deleted")
    private Integer isDeleted;
}
