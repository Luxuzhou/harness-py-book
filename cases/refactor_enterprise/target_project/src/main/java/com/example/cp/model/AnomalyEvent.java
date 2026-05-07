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
 * 异常事件记录实体
 * <p>
 * 映射到 anomaly_event 表，存储由 Python 分析引擎触发的异常预警事件。
 * 包含触发时的路径依从率序列和超限点位信息（以 JSON 格式存储）。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("anomaly_event")
public class AnomalyEvent {

    /** 事件ID（自增主键） */
    @Id
    @Column("id")
    private Long id;

    /** 关联的预警规则ID */
    @Column("rule_id")
    private Long ruleId;

    /** 诊疗项目ID */
    @Column("test_item_id")
    private String testItemId;

    /** 异常预警触发时间 */
    @Column("triggered_at")
    private LocalDateTime triggeredAt;

    /** 严重程度：WARNING / CRITICAL */
    @Column("severity")
    private String severity;

    /** 触发时的路径依从率序列（JSON数组字符串） */
    @Column("moving_averages")
    private String movingAverages;

    /** 超限点位信息（JSON数组字符串） */
    @Column("deviation_points")
    private String deviationPoints;

    /** 异常预警描述信息 */
    @Column("message")
    private String message;

    /** 是否已确认（1=已确认，0=未确认） */
    @Column("acknowledged")
    private Boolean acknowledged;

    /** 确认人 */
    @Column("acknowledged_by")
    private String acknowledgedBy;

    /** 确认时间 */
    @Column("acknowledged_at")
    private LocalDateTime acknowledgedAt;

    /** 创建时间 */
    @Column("created_at")
    private LocalDateTime createdAt;
}
