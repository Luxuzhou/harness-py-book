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
 * 质控项目移动均值实体
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("sqc_item_moving_avg")
public class SqcItemMovingAvg {

    @Id
    @Column("id")
    private String id;

    /** 关联的计划ID */
    @Column("plan_id")
    private String planId;

    /** 检验项目编码 */
    @Column("item_code")
    private String itemCode;

    /** 仪器编码 */
    @Column("instrument_code")
    private String instrumentCode;

    /** 移动均值 */
    @Column("avg_mean")
    private BigDecimal avgMean;

    /** 移动标准差 */
    @Column("avg_sd")
    private BigDecimal avgSd;

    /** 移动变异系数(%) */
    @Column("avg_cv")
    private BigDecimal avgCv;

    /** 参与计算的数据量 */
    @Column("data_count")
    private Integer dataCount;

    /** 计算日期 */
    @Column("calc_date")
    private LocalDate calcDate;

    /** 创建时间 */
    @Column("create_time")
    private LocalDateTime createTime;
}
