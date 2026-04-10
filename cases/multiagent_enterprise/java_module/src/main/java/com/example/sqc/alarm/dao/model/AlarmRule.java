package com.example.sqc.alarm.dao.model;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 智能报警规则 JPA 实体类。
 *
 * <p>映射到 alarm_rule 表。骨架代码 — Agent 需要补充：
 * <ul>
 *   <li>完善所有 @Column 注解（nullable, length, precision 等）</li>
 *   <li>添加 @Table(uniqueConstraints) 定义唯一约束</li>
 *   <li>字段的 getter/setter</li>
 *   <li>默认值设置</li>
 * </ul>
 *
 * <p>对应 DDL:
 * <pre>
 * CREATE TABLE alarm_rule (
 *     id              BIGINT AUTO_INCREMENT PRIMARY KEY,
 *     test_item_id    VARCHAR(64)   NOT NULL,
 *     test_item_name  VARCHAR(128)  NOT NULL,
 *     window_size     INT           NOT NULL DEFAULT 5,
 *     consecutive_count INT         NOT NULL DEFAULT 3,
 *     threshold_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.50,
 *     target_value    DECIMAL(10,4),
 *     sd_value        DECIMAL(10,4),
 *     enabled         TINYINT(1)    NOT NULL DEFAULT 1,
 *     created_at      DATETIME      NOT NULL,
 *     updated_at      DATETIME      NOT NULL
 * );
 * </pre>
 */
@Entity
@Table(name = "alarm_rule")
public class AlarmRule {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String testItemId;

    private String testItemName;

    private Integer windowSize;

    private Integer consecutiveCount;

    private BigDecimal thresholdMultiplier;

    private BigDecimal targetValue;

    private BigDecimal sdValue;

    private Boolean enabled;

    private LocalDateTime createdAt;

    private LocalDateTime updatedAt;

    // TODO: Agent 补充完整的 JPA 注解和 getter/setter
}
