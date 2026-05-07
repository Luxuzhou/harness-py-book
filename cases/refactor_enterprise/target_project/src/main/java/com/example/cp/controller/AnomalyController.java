package com.example.cp.controller;

import com.example.cp.dto.anomaly.AnomalyEventCreateRequest;
import com.example.cp.dto.anomaly.AnomalyEventResponse;
import com.example.cp.dto.anomaly.AnomalyRuleCreateRequest;
import com.example.cp.dto.anomaly.AnomalyRuleResponse;
import com.example.cp.service.anomaly.AnomalyService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 智能异常预警接口
 * <p>
 * 提供预警规则管理和异常事件记录的 REST API，
 * 供 Python 分析引擎调用。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/anomaly")
@RequiredArgsConstructor
@Validated
@Tag(name = "智能异常预警", description = "路径依从率预警规则管理与异常事件记录")
public class AnomalyController {

    private final AnomalyService anomalyService;

    @Value("${cp.service.token:default-service-token}")
    private String expectedServiceToken;

    // ====================================================================
    //                         预警规则管理
    // ====================================================================

    @PostMapping("/rules")
    @Operation(summary = "创建预警规则", description = "为指定诊疗项目创建路径依从率预警规则")
    public ResponseEntity<Map<String, Object>> createRule(
            @Valid @RequestBody AnomalyRuleCreateRequest request) {
        log.info("创建预警规则请求, testItemId={}", request.getTestItemId());
        try {
            AnomalyRuleResponse response = anomalyService.createRule(request);
            return ResponseEntity.status(HttpStatus.CREATED)
                    .body(Map.of("code", 201, "message", "规则创建成功", "data", response));
        } catch (IllegalStateException e) {
            log.warn("创建预警规则冲突: {}", e.getMessage());
            return ResponseEntity.status(HttpStatus.CONFLICT)
                    .body(Map.of("error_code", "RULE_ALREADY_EXISTS", "message", e.getMessage()));
        }
    }

    @GetMapping("/rules/{testItemId}")
    @Operation(summary = "查询预警规则", description = "根据诊疗项目ID查询其预警规则配置")
    public ResponseEntity<Map<String, Object>> getRule(
            @PathVariable
            @Parameter(description = "诊疗项目ID", example = "GLU-001")
            String testItemId) {
        log.info("查询预警规则请求, testItemId={}", testItemId);
        AnomalyRuleResponse response = anomalyService.getRule(testItemId);
        if (response == null) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND)
                    .body(Map.of("error_code", "RULE_NOT_FOUND",
                            "message", "未找到该诊疗项目的预警规则: " + testItemId));
        }
        return ResponseEntity.ok(Map.of("code", 200, "message", "查询成功", "data", response));
    }

    // ====================================================================
    //                         异常事件记录
    // ====================================================================

    @PostMapping("/events")
    @Operation(summary = "记录异常事件", description = "由 Python 分析引擎调用，当检测到异常预警条件时记录异常事件")
    public ResponseEntity<Map<String, Object>> createEvent(
            @RequestHeader("X-Service-Token") String serviceToken,
            @Valid @RequestBody AnomalyEventCreateRequest request) {
        log.info("记录异常事件请求, ruleId={}, testItemId={}", request.getRuleId(), request.getTestItemId());

        if (!expectedServiceToken.equals(serviceToken)) {
            log.warn("Service Token 认证失败");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                    .body(Map.of("error_code", "AUTH_FAILED", "message", "无效的 Service Token"));
        }

        AnomalyEventResponse response = anomalyService.createEvent(request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(Map.of("code", 201, "message", "异常事件记录成功", "data", response));
    }
}
