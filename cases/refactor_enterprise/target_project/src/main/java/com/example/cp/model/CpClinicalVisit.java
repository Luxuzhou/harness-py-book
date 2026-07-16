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
 * 临床路径诊疗样本实体
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_visit_sample")
public class CpClinicalVisit {

    @Id
    @Column("id")
    private String id;

    /** 关联的计划ID */
    @Column("plan_id")
    private String planId;

    /** 样本条码 */
    @Column("sample_barcode")
    private String sampleBarcode;

    /** 诊疗环节编码 */
    @Column("item_code")
    private String itemCode;

    /** 科室编码 */
    @Column("instrument_code")
    private String instrumentCode;

    /** 临床路径品批号 */
    @Column("control_lot_no")
    private String controlLotNo;

    /** 临床路径品水平 */
    @Column("control_level")
    private Integer controlLevel;

    /** 诊疗结果值 */
    @Column("result_value")
    private BigDecimal resultValue;

    /** 结果单位 */
    @Column("result_unit")
    private String resultUnit;

    /** 临床路径判定结果 */
    @Column("qc_result")
    private String qcResult;

    /** 触发规则编码 */
    @Column("rule_code")
    private String ruleCode;

    /** Z-score值 */
    @Column("z_score")
    private BigDecimal zScore;

    /** 诊疗时间 */
    @Column("inspect_time")
    private LocalDateTime inspectTime;

    /** 操作人 */
    @Column("operator")
    private String operator;

    /** 是否删除 */
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
