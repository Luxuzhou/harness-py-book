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
 * 临床路径异常预警记录实体
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_anomaly_record")
public class CpAnomalyRecord {

    @Id
    @Column("id")
    private String id;

    @Column("plan_id")
    private String planId;

    @Column("item_code")
    private String itemCode;

    @Column("instrument_code")
    private String instrumentCode;

    @Column("lab_code")
    private String labCode;

    @Column("alarm_level")
    private String alarmLevel;

    @Column("alarm_level_name")
    private String alarmLevelName;

    @Column("rule_code")
    private String ruleCode;

    @Column("rule_name")
    private String ruleName;

    @Column("result_value")
    private BigDecimal resultValue;

    @Column("target_mean")
    private BigDecimal targetMean;

    @Column("target_sd")
    private BigDecimal targetSd;

    @Column("z_score")
    private BigDecimal zScore;

    @Column("alarm_message")
    private String alarmMessage;

    @Column("handle_status")
    private Integer handleStatus;

    @Column("handler")
    private String handler;

    @Column("handle_time")
    private LocalDateTime handleTime;

    @Column("handle_remark")
    private String handleRemark;

    @Column("alarm_time")
    private LocalDateTime alarmTime;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
