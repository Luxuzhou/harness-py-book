package com.example.cp.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 临床路径方案变更记录实体
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_pathway_change")
public class CpPathwayVariation {

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
