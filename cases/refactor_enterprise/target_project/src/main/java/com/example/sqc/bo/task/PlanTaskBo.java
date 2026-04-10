package com.example.sqc.bo.task;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 质控计划任务BO
 * <p>
 * 用于在服务层之间传递计划任务的运行时上下文信息。
 * </p>
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PlanTaskBo {

    private String planId;
    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private String algorithmCode;
    private Integer movingWindow;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private String controlLotNo;
    private Integer controlLevel;
    private String normalTransCode;
    private String tailProcessing;
    private Boolean excludeWeekend;
    private String taskStatus;
    private String errorMessage;
    private Integer retryCount;
    private LocalDateTime createTime;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private Long elapsedMs;
}
