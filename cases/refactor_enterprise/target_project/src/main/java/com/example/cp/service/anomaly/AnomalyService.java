package com.example.cp.service.anomaly;

import com.example.cp.dto.anomaly.AnomalyEventCreateRequest;
import com.example.cp.dto.anomaly.AnomalyEventResponse;
import com.example.cp.dto.anomaly.AnomalyRuleCreateRequest;
import com.example.cp.dto.anomaly.AnomalyRuleResponse;
import com.example.cp.mapper.AnomalyEventMapper;
import com.example.cp.mapper.AnomalyRuleMapper;
import com.example.cp.model.AnomalyEvent;
import com.example.cp.model.AnomalyRule;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * 智能异常预警业务服务
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AnomalyService {

    private final AnomalyRuleMapper anomalyRuleMapper;
    private final AnomalyEventMapper anomalyEventMapper;

    /**
     * 创建预警规则
     *
     * @param request 创建请求
     * @return 创建后的规则响应
     * @throws IllegalStateException 该诊疗项目已存在规则
     */
    @Transactional(rollbackFor = Exception.class)
    public AnomalyRuleResponse createRule(AnomalyRuleCreateRequest request) {
        if (anomalyRuleMapper.existsByTestItemId(request.getTestItemId())) {
            throw new IllegalStateException("该诊疗项目已存在预警规则: " + request.getTestItemId());
        }

        AnomalyRule rule = AnomalyRule.builder()
                .testItemId(request.getTestItemId())
                .testItemName(request.getTestItemName())
                .windowSize(request.getWindowSize())
                .consecutiveCount(request.getConsecutiveCount())
                .thresholdMultiplier(request.getThresholdMultiplier())
                .targetValue(request.getTargetValue())
                .sdValue(request.getSdValue())
                .enabled(request.getEnabled())
                .createdAt(LocalDateTime.now())
                .updatedAt(LocalDateTime.now())
                .build();

        anomalyRuleMapper.insert(rule);
        log.info("创建预警规则成功, testItemId={}, ruleId={}", request.getTestItemId(), rule.getId());
        return toRuleResponse(rule);
    }

    /**
     * 根据诊疗项目ID查询预警规则
     *
     * @param testItemId 诊疗项目ID
     * @return 预警规则响应，不存在时返回 null
     */
    @Transactional(readOnly = true)
    public AnomalyRuleResponse getRule(String testItemId) {
        AnomalyRule rule = anomalyRuleMapper.findByTestItemId(testItemId);
        if (rule == null) {
            return null;
        }
        return toRuleResponse(rule);
    }

    /**
     * 记录异常事件
     *
     * @param request 异常事件创建请求
     * @return 创建的异常事件响应
     */
    @Transactional(rollbackFor = Exception.class)
    public AnomalyEventResponse createEvent(AnomalyEventCreateRequest request) {
        String movingAveragesJson = null;
        String deviationPointsJson = null;

        if (request.getMovingAverages() != null) {
            movingAveragesJson = request.getMovingAverages().toString();
        }
        if (request.getDeviationPoints() != null) {
            deviationPointsJson = request.getDeviationPoints().toString();
        }

        AnomalyEvent event = AnomalyEvent.builder()
                .ruleId(request.getRuleId())
                .testItemId(request.getTestItemId())
                .triggeredAt(request.getTriggeredAt())
                .severity(request.getSeverity())
                .movingAverages(movingAveragesJson)
                .deviationPoints(deviationPointsJson)
                .message(request.getMessage())
                .acknowledged(false)
                .createdAt(LocalDateTime.now())
                .build();

        anomalyEventMapper.insert(event);
        log.info("记录异常事件成功, eventId={}, testItemId={}, severity={}",
                event.getId(), event.getTestItemId(), event.getSeverity());
        return toEventResponse(event);
    }

    // ====================================================================
    //                         Entity <-> DTO 转换
    // ====================================================================

    private AnomalyRuleResponse toRuleResponse(AnomalyRule rule) {
        if (rule == null) {
            return null;
        }
        return AnomalyRuleResponse.builder()
                .id(rule.getId())
                .testItemId(rule.getTestItemId())
                .testItemName(rule.getTestItemName())
                .windowSize(rule.getWindowSize())
                .consecutiveCount(rule.getConsecutiveCount())
                .thresholdMultiplier(rule.getThresholdMultiplier())
                .targetValue(rule.getTargetValue())
                .sdValue(rule.getSdValue())
                .enabled(rule.getEnabled())
                .createdAt(rule.getCreatedAt())
                .updatedAt(rule.getUpdatedAt())
                .build();
    }

    private AnomalyEventResponse toEventResponse(AnomalyEvent event) {
        if (event == null) {
            return null;
        }
        return AnomalyEventResponse.builder()
                .id(event.getId())
                .ruleId(event.getRuleId())
                .testItemId(event.getTestItemId())
                .triggeredAt(event.getTriggeredAt())
                .severity(event.getSeverity())
                .message(event.getMessage())
                .createdAt(event.getCreatedAt())
                .build();
    }
}
