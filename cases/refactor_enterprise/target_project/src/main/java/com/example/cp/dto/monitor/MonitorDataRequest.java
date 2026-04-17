package com.example.cp.dto.monitor;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 偏差监测数据请求
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MonitorDataRequest {

    @NotBlank(message = "实验室编码不能为空")
    private String labCode;

    private String instrumentCode;

    private String itemCode;

    private String planId;

    @NotNull(message = "诊疗结果不能为空")
    private BigDecimal resultValue;

    private LocalDateTime inspectTime;

    private LocalDate startDate;

    private LocalDate endDate;

    private String alarmLevel;

    private Integer pageNum = 1;

    private Integer pageSize = 20;
}
