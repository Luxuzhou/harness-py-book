package com.example.sqc.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 质控计划变更记录实体
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("sqc_moving_change")
public class SqcMovingChange {

    @Id
    @Column("id")
    private String id;

    /** 关联的计划ID */
    @Column("plan_id")
    private String planId;

    /** 变更字段名 */
    @Column("field_name")
    private String fieldName;

    /** 变更前的值 */
    @Column("old_value")
    private String oldValue;

    /** 变更后的值 */
    @Column("new_value")
    private String newValue;

    /** 操作人 */
    @Column("operator")
    private String operator;

    /** 变更时间 */
    @Column("change_time")
    private LocalDateTime changeTime;

    /** 变更原因 */
    @Column("change_reason")
    private String changeReason;

    /** 创建时间 */
    @Column("create_time")
    private LocalDateTime createTime;
}
