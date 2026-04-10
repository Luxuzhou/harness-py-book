package com.example.sqc.alarm.dto;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 报警规则数据传输对象。
 *
 * <p>骨架代码 — Agent 需要补充：
 * <ul>
 *   <li>Bean Validation 注解（@NotNull, @NotBlank, @Min, @Max, @DecimalMin, @DecimalMax）</li>
 *   <li>与 api_contract.yaml 中 AlarmRuleCreateRequest / AlarmRuleResponse 的字段一一对应</li>
 *   <li>Jackson 注解（如需要覆盖全局 snake_case 策略）</li>
 *   <li>getter/setter</li>
 * </ul>
 *
 * <p>字段约束（来自契约）：
 * <ul>
 *   <li>test_item_id: required, maxLength=64</li>
 *   <li>test_item_name: required, maxLength=128</li>
 *   <li>window_size: 3~20, default=5</li>
 *   <li>consecutive_count: 2~10, default=3</li>
 *   <li>threshold_multiplier: 0.5~3.0, default=1.5</li>
 *   <li>target_value: required</li>
 *   <li>sd_value: required</li>
 *   <li>enabled: default=true</li>
 * </ul>
 */
public class AlarmRuleDto {

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

    // TODO: Agent 补充 validation 注解和 getter/setter
}
