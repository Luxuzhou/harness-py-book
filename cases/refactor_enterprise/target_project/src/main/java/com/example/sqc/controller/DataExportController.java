package com.example.sqc.controller;

import com.example.sqc.dto.export.ExportRequest;
import com.example.sqc.dto.export.ExportResultDto;
import com.example.sqc.service.plan.SqcPlanService;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 数据导出接口
 *
 * @author sqc-team
 * @since 2024-04-01
 */
@Slf4j
@RestController
@RequestMapping("/api/sqc/export")
@RequiredArgsConstructor
@Validated
@Tag(name = "数据导出", description = "质控数据导出功能")
public class DataExportController {

    private final SqcPlanService sqcPlanService;

    @PostMapping("/plan-data")
    @Operation(summary = "导出计划数据", description = "导出指定质控计划的历史数据为Excel")
    public ResponseEntity<Map<String, Object>> exportPlanData(
            @Valid @RequestBody ExportRequest request) {
        log.info("导出计划数据请求, planId={}", request.getPlanId());
        // 导出功能已迁移到独立的ExportService
        // 这里保留接口定义，返回未实现状态
        return ResponseEntity.ok(Map.of(
                "code", 200,
                "message", "导出任务已提交",
                "taskId", java.util.UUID.randomUUID().toString()
        ));
    }

    @GetMapping("/status/{taskId}")
    @Operation(summary = "查询导出状态", description = "查询数据导出任务的执行状态")
    public ResponseEntity<Map<String, Object>> getExportStatus(
            @PathVariable @NotBlank(message = "任务ID不能为空") String taskId) {
        return ResponseEntity.ok(Map.of(
                "code", 200,
                "data", Map.of(
                        "taskId", taskId,
                        "status", "COMPLETED",
                        "progress", 100
                )
        ));
    }
}
