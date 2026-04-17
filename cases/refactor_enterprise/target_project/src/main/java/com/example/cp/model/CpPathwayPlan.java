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
 * 临床路径路径依从率计划实体
 * <p>
 * 对应数据库表cp_pathway_plan，存储临床路径方案的核心配置信息。
 * 每个计划对应一个科室上的一个诊疗环节的临床路径方案。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_pathway_plan")
public class CpPathwayPlan {

    /** 主键ID */
    @Id
    @Column("id")
    private String id;

    /** 实验室编码 */
    @Column("lab_code")
    private String labCode;

    /** 实验室名称 */
    @Column("lab_name")
    private String labName;

    /** 科室编码 */
    @Column("instrument_code")
    private String instrumentCode;

    /** 科室名称 */
    @Column("instrument_name")
    private String instrumentName;

    /** 诊疗环节编码 */
    @Column("item_code")
    private String itemCode;

    /** 诊疗环节名称 */
    @Column("item_name")
    private String itemName;

    /** 诊疗环节英文缩写 */
    @Column("item_abbr")
    private String itemAbbr;

    /** 临床路径品批号 */
    @Column("control_lot_no")
    private String controlLotNo;

    /** 临床路径品水平（1=低值, 2=正常值, 3=高值） */
    @Column("control_level")
    private Integer controlLevel;

    /** 临床路径品名称 */
    @Column("control_name")
    private String controlName;

    /** 算法编码 */
    @Column("algorithm_code")
    private String algorithmCode;

    /** 算法名称 */
    @Column("algorithm_name")
    private String algorithmName;

    /** 移动窗口大小 */
    @Column("moving_window")
    private Integer movingWindow;

    /** 目标均值（靶值） */
    @Column("target_mean")
    private BigDecimal targetMean;

    /** 目标标准差 */
    @Column("target_sd")
    private BigDecimal targetSd;

    /** 目标变异系数(%) */
    @Column("target_cv")
    private BigDecimal targetCv;

    /** 计算均值 */
    @Column("calc_mean")
    private BigDecimal calcMean;

    /** 计算标准差 */
    @Column("calc_sd")
    private BigDecimal calcSd;

    /** 计算变异系数 */
    @Column("calc_cv")
    private BigDecimal calcCv;

    /** 数据量 */
    @Column("data_count")
    private Integer dataCount;

    /** 正态转换算法编码 */
    @Column("normal_trans_code")
    private String normalTransCode;

    /** 正态转换算法名称 */
    @Column("normal_trans_name")
    private String normalTransName;

    /** 尾数处理方式 */
    @Column("tail_processing")
    private String tailProcessing;

    /** 是否排除周末数据 */
    @Column("exclude_weekend")
    private Boolean excludeWeekend;

    /** 计划状态（0=禁用, 1=启用） */
    @Column("plan_status")
    private Integer planStatus;

    /** 最后计算时间 */
    @Column("last_calc_time")
    private LocalDateTime lastCalcTime;

    /** 创建人 */
    @Column("creator")
    private String creator;

    /** 更新人 */
    @Column("updater")
    private String updater;

    /** 是否删除（0=否, 1=是） */
    @Column("is_deleted")
    private Integer isDeleted;

    /** 创建时间 */
    @Column("create_time")
    private LocalDateTime createTime;

    /** 更新时间 */
    @Column("update_time")
    private LocalDateTime updateTime;

    /** 备注 */
    @Column("remark")
    private String remark;
}
