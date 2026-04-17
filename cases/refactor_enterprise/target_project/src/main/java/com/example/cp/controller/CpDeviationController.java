package com.example.cp.controller;

import com.example.cp.dto.monitor.MonitorAlarmDto;
import com.example.cp.dto.monitor.MonitorDataRequest;
import com.example.cp.service.monitor.CpDeviationService;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 临床路径偏差监测接口
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Slf4j
@RestController
@RequestMapping("/api/cp/monitor")
@RequiredArgsConstructor
@Validated
@Tag(name = "临床路径偏差监测", description = "临床路径数据实时偏差监测、异常预警管理、仪表盘数据")
public class CpDeviationController {

    private final CpDeviationService cpDeviationService;

    @PostMapping("/check")
    @Operation(summary = "实时检查临床路径结果", description = "检查单个临床路径结果是否失控")
    public ResponseEntity<Map<String, Object>> checkQcResult(
            @RequestParam @NotBlank(message = "计划ID不能为空") String planId,
            @RequestParam @Parameter(description = "诊疗结果值") BigDecimal resultValue,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
                @Parameter(description = "诊疗时间") LocalDateTime inspectTime) {

        if (inspectTime == null) {
            inspectTime = LocalDateTime.now();
        }
        MonitorAlarmDto alarm = cpDeviationService.checkQcResult(planId, resultValue, inspectTime);
        return ResponseEntity.ok(Map.of("code", 200, "data", alarm != null ? alarm : Map.of()));
    }

    @GetMapping("/dashboard")
    @Operation(summary = "获取偏差监测仪表盘", description = "获取临床路径偏差监测仪表盘汇总数据")
    public ResponseEntity<Map<String, Object>> getDashboard(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "日期，默认今天") LocalDate date) {

        if (date == null) {
            date = LocalDate.now();
        }
        Map<String, Object> dashboard = cpDeviationService.getDashboardData(labCode, date);
        return ResponseEntity.ok(Map.of("code", 200, "data", dashboard));
    }

    @GetMapping("/alarms/recent")
    @Operation(summary = "获取最近异常预警", description = "获取指定实验室最近的临床路径异常预警列表")
    public ResponseEntity<Map<String, Object>> getRecentAlarms(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam(defaultValue = "20") @Parameter(description = "返回条数") Integer limit) {

        List<MonitorAlarmDto> alarms = cpDeviationService.getRecentAlarms(labCode, limit);
        return ResponseEntity.ok(Map.of("code", 200, "data", alarms));
    }

    @GetMapping("/task/status/{planId}")
    @Operation(summary = "查询任务状态", description = "查询指定计划的偏差监测任务运行状态")
    public ResponseEntity<Map<String, Object>> getTaskStatus(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId) {

        boolean running = cpDeviationService.hasRunningTask(planId);
        return ResponseEntity.ok(Map.of("code", 200, "data", Map.of(
                "planId", planId,
                "running", running,
                "status", running ? "RUNNING" : "IDLE"
        )));
    }

    @PostMapping("/task/refresh/{planId}")
    @Operation(summary = "刷新偏差监测配置", description = "刷新指定计划的偏差监测配置缓存")
    public ResponseEntity<Map<String, Object>> refreshPlanConfig(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId) {

        cpDeviationService.refreshPlanConfig(planId);
        return ResponseEntity.ok(Map.of("code", 200, "message", "配置刷新成功"));
    }
}
