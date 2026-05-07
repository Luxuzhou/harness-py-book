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
 * 智能预警规则配置实体
 * <p>
 * 映射到 anomaly_rule 表，存储路径依从率预警规则的配置参数。
 * 每个诊疗项目最多只能有一条预警规则（由 test_item_id 唯一约束保证）。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("anomaly_rule")
public class AnomalyRule {

    /** 规则ID（自增主键） */
    @Id
    @Column("id")
    private Long id;

    /** 诊疗项目ID（唯一约束） */
    @Column("test_item_id")
    private String testItemId;

    /** 诊疗项目名称 */
    @Column("test_item_name")
    private String testItemName;

    /** 路径依从率窗口大小（3~20） */
    @Column("window_size")
    private Integer windowSize;

    /** 连续超限判定次数（2~10） */
    @Column("consecutive_count")
    private Integer consecutiveCount;

    /** 控制限倍数（相对于SD，0.5~3.0） */
    @Column("threshold_multiplier")
    private BigDecimal thresholdMultiplier;

    /** 目标值（靶值） */
    @Column("target_value")
    private BigDecimal targetValue;

    /** 标准差 */
    @Column("sd_value")
    private BigDecimal sdValue;

    /** 是否启用（1=启用，0=禁用） */
    @Column("enabled")
    private Boolean enabled;

    /** 创建时间 */
    @Column("created_at")
    private LocalDateTime createdAt;

    /** 更新时间 */
    @Column("updated_at")
    private LocalDateTime updatedAt;
}
