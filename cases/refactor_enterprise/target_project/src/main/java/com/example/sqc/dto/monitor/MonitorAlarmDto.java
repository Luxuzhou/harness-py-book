package com.example.sqc.dto.monitor;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 质控报警DTO
 *
 * @author sqc-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MonitorAlarmDto implements Serializable {

    private static final long serialVersionUID = 1L;

    private String id;
    private String planId;
    private String itemCode;
    private String itemName;
    private String instrumentCode;
    private String instrumentName;
    private String labCode;
    private String alarmLevel;
    private String alarmLevelName;
    private String ruleCode;
    private String ruleName;
    private BigDecimal resultValue;
    private BigDecimal targetMean;
    private BigDecimal targetSd;
    private BigDecimal zScore;
    private String alarmMessage;
    private Integer handleStatus;
    private String handler;
    private LocalDateTime handleTime;
    private String handleRemark;
    private LocalDateTime inspectTime;
    private LocalDateTime alarmTime;
    private LocalDateTime checkTime;
}
