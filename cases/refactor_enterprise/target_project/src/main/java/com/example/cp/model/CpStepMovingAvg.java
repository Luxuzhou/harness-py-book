package com.example.cp.model;

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
 * 临床路径项目路径依从率实体
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_step_moving_avg")
public class CpComplianceRate {

    @Id
    @Column("id")
    private String id;

    /** 关联的计划ID */
    @Column("plan_id")
    private String planId;

    /** 诊疗环节编码 */
    @Column("item_code")
    private String itemCode;

    /** 科室编码 */
    @Column("instrument_code")
    private String instrumentCode;

    /** 路径依从率 */
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
