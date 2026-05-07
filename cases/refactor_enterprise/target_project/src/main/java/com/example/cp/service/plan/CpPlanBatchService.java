package com.example.cp.service.plan;

import com.example.cp.dto.plan.CpPlanApplyRequest;
import com.example.cp.dto.plan.CpPlanBatchRequest;
import com.example.cp.mapper.CpPathwayPlanMapper;
import com.example.cp.model.CpPathwayPlan;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.CollectionUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.*;

/**
 * 临床路径方案批量操作服务
 * <p>
 * 负责批量启用/禁用计划、批量执行临床路径计算等批量操作。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanBatchService {

    private final CpPathwayPlanMapper cpPathwayPlanMapper;
    private final CpPlanCacheService cpPlanCacheService;
    private final CpPlanCalculationService cpPlanCalculationService;

    private static final ExecutorService PLAN_CALC_POOL = Executors.newFixedThreadPool(3);

    /**
     * 批量启用/禁用计划
     */
    @Transactional(rollbackFor = Exception.class)
    public int batchUpdatePlanStatus(CpPlanBatchRequest request) {
        if (CollectionUtils.isEmpty(request.getPlanIds())) {
            return 0;
        }

        int count = 0;
        for (String planId : request.getPlanIds()) {
            CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
            if (plan != null && plan.getIsDeleted() == 0) {
                plan.setPlanStatus(request.getTargetStatus());
                plan.setUpdateTime(LocalDateTime.now());
                plan.setUpdater(request.getOperator());
                cpPathwayPlanMapper.update(plan);
                count++;

                // 清除单个计划缓存
                cpPlanCacheService.clearPlanCache(planId);
            }
        }

        log.info("批量更新计划状态完成, 目标状态={}, 成功数={}", request.getTargetStatus(), count);
        return count;
    }

    /**
     * 批量执行临床路径计算
     */
    public List<Map<String, Object>> batchExecutePlanCalc(List<String> planIds) {
        if (CollectionUtils.isEmpty(planIds)) {
            return Collections.emptyList();
        }

        List<Future<Map<String, Object>>> futures = new ArrayList<>();

        for (String planId : planIds) {
            Future<Map<String, Object>> future = PLAN_CALC_POOL.submit(() -> {
                try {
                    CpPathwayPlan plan = cpPathwayPlanMapper.selectOneById(planId);
                    if (plan == null || plan.getIsDeleted() == 1 || plan.getPlanStatus() != 1) {
                        Map<String, Object> skip = new HashMap<>();
                        skip.put("planId", planId);
                        skip.put("success", false);
                        skip.put("message", "计划不存在或已禁用");
                        return skip;
                    }

                    CpPlanApplyRequest request = CpPlanApplyRequest.builder()
                            .planId(plan.getId())
                            .labCode(plan.getLabCode())
                            .instrumentCode(plan.getInstrumentCode())
                            .itemCode(plan.getItemCode())
                            .controlLotNo(plan.getControlLotNo())
                            .controlLevel(plan.getControlLevel())
                            .algorithmCode(plan.getAlgorithmCode())
                            .movingWindow(plan.getMovingWindow())
                            .targetMean(plan.getTargetMean())
                            .targetSd(plan.getTargetSd())
                            .normalTransCode(plan.getNormalTransCode())
                            .tailProcessing(plan.getTailProcessing())
                            .excludeWeekend(plan.getExcludeWeekend())
                            .startDate(LocalDate.now().minusDays(30))
                            .endDate(LocalDate.now())
                            .build();

                    return cpPlanCalculationService.applyCpPathwayPlan(request);
                } catch (Exception e) {
                    log.error("批量计算失败, planId={}", planId, e);
                    Map<String, Object> error = new HashMap<>();
                    error.put("planId", planId);
                    error.put("success", false);
                    error.put("message", e.getMessage());
                    return error;
                }
            });
            futures.add(future);
        }

        List<Map<String, Object>> results = new ArrayList<>();
        for (Future<Map<String, Object>> future : futures) {
            try {
                results.add(future.get(60, TimeUnit.SECONDS));
            } catch (Exception e) {
                Map<String, Object> timeout = new HashMap<>();
                timeout.put("success", false);
                timeout.put("message", "计算超时");
                results.add(timeout);
            }
        }

        return results;
    }
}
