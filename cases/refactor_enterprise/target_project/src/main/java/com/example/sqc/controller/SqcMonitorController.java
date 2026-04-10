package com.example.sqc.controller;

import com.example.sqc.dto.monitor.MonitorAlarmDto;
import com.example.sqc.dto.monitor.MonitorDataRequest;
import com.example.sqc.service.monitor.SqcMonitorService;

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
 * 质控监控接口
 *
 * @author sqc-team
 * @since 2024-03-20
 */
@Slf4j
@RestController
@RequestMapping("/api/sqc/monitor")
@RequiredArgsConstructor
@Validated
@Tag(name = "质控监控", description = "质控数据实时监控、报警管理、仪表盘数据")
public class SqcMonitorController {

    private final SqcMonitorService sqcMonitorService;

    @PostMapping("/check")
    @Operation(summary = "实时检查质控结果", description = "检查单个质控结果是否失控")
    public ResponseEntity<Map<String, Object>> checkQcResult(
            @RequestParam @NotBlank(message = "计划ID不能为空") String planId,
            @RequestParam @Parameter(description = "检验结果值") BigDecimal resultValue,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd HH:mm:ss")
                @Parameter(description = "检验时间") LocalDateTime inspectTime) {

        if (inspectTime == null) {
            inspectTime = LocalDateTime.now();
        }
        MonitorAlarmDto alarm = sqcMonitorService.checkQcResult(planId, resultValue, inspectTime);
        return ResponseEntity.ok(Map.of("code", 200, "data", alarm != null ? alarm : Map.of()));
    }

    @GetMapping("/dashboard")
    @Operation(summary = "获取监控仪表盘", description = "获取质控监控仪表盘汇总数据")
    public ResponseEntity<Map<String, Object>> getDashboard(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam(required = false) @DateTimeFormat(pattern = "yyyy-MM-dd")
                @Parameter(description = "日期，默认今天") LocalDate date) {

        if (date == null) {
            date = LocalDate.now();
        }
        Map<String, Object> dashboard = sqcMonitorService.getDashboardData(labCode, date);
        return ResponseEntity.ok(Map.of("code", 200, "data", dashboard));
    }

    @GetMapping("/alarms/recent")
    @Operation(summary = "获取最近报警", description = "获取指定实验室最近的质控报警列表")
    public ResponseEntity<Map<String, Object>> getRecentAlarms(
            @RequestParam @NotBlank(message = "实验室编码不能为空") String labCode,
            @RequestParam(defaultValue = "20") @Parameter(description = "返回条数") Integer limit) {

        List<MonitorAlarmDto> alarms = sqcMonitorService.getRecentAlarms(labCode, limit);
        return ResponseEntity.ok(Map.of("code", 200, "data", alarms));
    }

    @GetMapping("/task/status/{planId}")
    @Operation(summary = "查询任务状态", description = "查询指定计划的监控任务运行状态")
    public ResponseEntity<Map<String, Object>> getTaskStatus(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId) {

        boolean running = sqcMonitorService.hasRunningTask(planId);
        return ResponseEntity.ok(Map.of("code", 200, "data", Map.of(
                "planId", planId,
                "running", running,
                "status", running ? "RUNNING" : "IDLE"
        )));
    }

    @PostMapping("/task/refresh/{planId}")
    @Operation(summary = "刷新监控配置", description = "刷新指定计划的监控配置缓存")
    public ResponseEntity<Map<String, Object>> refreshPlanConfig(
            @PathVariable @NotBlank(message = "计划ID不能为空") String planId) {

        sqcMonitorService.refreshPlanConfig(planId);
        return ResponseEntity.ok(Map.of("code", 200, "message", "配置刷新成功"));
    }
}
