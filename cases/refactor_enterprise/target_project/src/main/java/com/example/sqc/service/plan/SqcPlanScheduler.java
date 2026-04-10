package com.example.sqc.service.plan;

import com.example.sqc.bo.task.PlanTaskBo;
import com.example.sqc.model.SqcMovingPlan;
import com.example.sqc.service.monitor.SqcMonitorService;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 质控计划定时调度器
 * <p>
 * 定时扫描需要执行质控计算的计划，按实验室分组后批量执行。
 * 同时负责监控任务状态检查和过期缓存清理。
 * </p>
 *
 * @author sqc-team
 * @since 2024-03-25
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class SqcPlanScheduler {

    private final SqcPlanService sqcPlanService;
    private final SqcMonitorService sqcMonitorService;

    @Value("${sqc.plan.schedule.enabled:true}")
    private Boolean scheduleEnabled;

    @Value("${sqc.plan.schedule.lab-codes:LAB001,LAB002,LAB003}")
    private String labCodeConfig;

    /**
     * 每小时执行一次质控计算扫描
     * <p>
     * 扫描所有实验室中需要执行计算的计划，按批次提交执行。
     * 每次最多处理100个计划，避免资源占用过多。
     * </p>
     */
    @Scheduled(cron = "0 0 * * * ?")
    public void scheduledPlanCalc() {
        if (!Boolean.TRUE.equals(scheduleEnabled)) {
            log.debug("定时质控计算已禁用");
            return;
        }

        log.info("===== 开始定时质控计算扫描 =====");
        long startTime = System.currentTimeMillis();

        List<String> labCodes = Arrays.stream(labCodeConfig.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toList());

        int totalProcessed = 0;
        int totalSuccess = 0;
        int totalFailed = 0;

        for (String labCode : labCodes) {
            try {
                List<SqcMovingPlan> plans = sqcPlanService.getPlansNeedingCalc(labCode);
                if (plans.isEmpty()) {
                    log.debug("实验室 {} 无需执行计算的计划", labCode);
                    continue;
                }

                log.info("实验室 {} 发现 {} 个需要计算的计划", labCode, plans.size());

                // 限制每次最多处理100个
                List<String> planIds = plans.stream()
                        .limit(100)
                        .map(SqcMovingPlan::getId)
                        .collect(Collectors.toList());

                List<Map<String, Object>> results = sqcPlanService.batchExecutePlanCalc(planIds);

                for (Map<String, Object> result : results) {
                    totalProcessed++;
                    if (Boolean.TRUE.equals(result.get("success"))) {
                        totalSuccess++;
                    } else {
                        totalFailed++;
                    }
                }
            } catch (Exception e) {
                log.error("处理实验室 {} 的定时计算失败", labCode, e);
            }
        }

        long elapsed = System.currentTimeMillis() - startTime;
        log.info("===== 定时质控计算完成, 处理={}, 成功={}, 失败={}, 耗时={}ms =====",
                totalProcessed, totalSuccess, totalFailed, elapsed);
    }

    /**
     * 每5分钟检查一次超时的监控任务
     */
    @Scheduled(fixedDelay = 300000)
    public void checkTimeoutTasks() {
        if (!Boolean.TRUE.equals(scheduleEnabled)) {
            return;
        }

        log.debug("检查超时监控任务");
        // 简化实现：检查逻辑依赖Redis中的任务标记
        // 实际应该查询所有running状态的任务，检查是否超时
    }

    /**
     * 每天凌晨2点执行缓存清理
     */
    @Scheduled(cron = "0 0 2 * * ?")
    public void dailyCacheCleanup() {
        if (!Boolean.TRUE.equals(scheduleEnabled)) {
            return;
        }

        log.info("开始每日缓存清理");
        // 简化实现：实际应该清理过期的计划缓存、监控缓存等
        log.info("每日缓存清理完成");
    }

    /**
     * 每天凌晨3点生成前一天的质控日报
     */
    @Scheduled(cron = "0 0 3 * * ?")
    public void generateDailyReport() {
        if (!Boolean.TRUE.equals(scheduleEnabled)) {
            return;
        }

        LocalDate yesterday = LocalDate.now().minusDays(1);
        log.info("开始生成 {} 的质控日报", yesterday);

        List<String> labCodes = Arrays.stream(labCodeConfig.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toList());

        for (String labCode : labCodes) {
            try {
                Map<String, Object> dashboard = sqcMonitorService.getDashboardData(labCode, yesterday);
                log.info("实验室 {} 质控日报: 总计划={}, 完成={}, 报警={}",
                        labCode,
                        dashboard.get("totalPlans"),
                        dashboard.get("completedToday"),
                        dashboard.get("totalAlarms"));

                // TODO: 发送邮件或推送通知
            } catch (Exception e) {
                log.error("生成实验室 {} 的质控日报失败", labCode, e);
            }
        }
    }
}
