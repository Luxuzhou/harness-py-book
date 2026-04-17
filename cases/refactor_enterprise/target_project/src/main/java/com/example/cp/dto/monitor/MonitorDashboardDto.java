package com.example.cp.dto.monitor;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 偏差监测仪表盘DTO
 *
 * @author cp-team
 * @since 2024-03-25
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MonitorDashboardDto {

    private Long totalPlans;
    private Long activePlans;
    private Long completedToday;
    private Long pendingToday;
    private BigDecimal completionRate;
    private Map<String, Integer> alarmStats;
    private Integer totalAlarms;
    private List<MonitorAlarmDto> recentAlarms;
    private String updateTime;
}
