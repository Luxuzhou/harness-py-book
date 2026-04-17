package com.example.cp.dto.monitor;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 偏差监测任务DTO
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MonitorTaskDto {

    private String taskId;
    private String planId;
    private String labCode;
    private String instrumentCode;
    private String itemCode;
    private String taskType;
    private String taskStatus;
    private String taskStatusName;
    private String errorMessage;
    private Integer retryCount;
    private Integer alarmCount;
    private LocalDateTime createTime;
    private LocalDateTime startTime;
    private LocalDateTime endTime;
    private Long elapsedMs;
}
