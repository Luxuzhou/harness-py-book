package com.example.sqc.service.monitor;

import com.example.sqc.bo.task.MonitorTaskBo;
import com.example.sqc.dto.monitor.MonitorAlarmDto;
import com.example.sqc.dto.monitor.MonitorDataRequest;
import com.example.sqc.enums.monitor.AlarmLevelEnum;
import com.example.sqc.enums.monitor.MonitorStatusEnum;
import com.example.sqc.exception.SqcBusinessException;
import com.example.sqc.exception.CommonErrorCode;
import com.example.sqc.mapper.SqcMovingPlanMapper;
import com.example.sqc.mapper.SqcItemMovingAvgMapper;
import com.example.sqc.mapper.SqcInspectSampleMapper;
import com.example.sqc.mapper.ck.BiInspectResultMapper;
import com.example.sqc.model.SqcMovingPlan;
import com.example.sqc.model.SqcItemMovingAvg;
import com.example.sqc.model.SqcInspectSample;
import com.example.sqc.model.ck.BiInspectResult;
import com.example.sqc.queue.RedisQueueService1;

import com.mybatisflex.core.query.QueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import javax.annotation.Resource;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * 质控监控服务
 * <p>
 * 负责质控数据的实时监控，包括：
 * - 质控结果的实时监测与报警生成
 * - 失控事件的跟踪与处理
 * - 监控仪表盘数据聚合
 * - 定时巡检任务的调度
 * </p>
 *
 * @author sqc-team
 * @since 2024-03-20
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SqcMonitorService {

    private final SqcMovingPlanMapper sqcMovingPlanMapper;
    private final SqcItemMovingAvgMapper sqcItemMovingAvgMapper;
    private final SqcInspectSampleMapper sqcInspectSampleMapper;
    private final BiInspectResultMapper biInspectResultMapper;

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Resource
    private RedisQueueService1 redisQueueService;

    private static final String MONITOR_CACHE_PREFIX = "sqc:monitor:";
    private static final String ALARM_CACHE_PREFIX = "sqc:alarm:";
    private static final String TASK_RUNNING_KEY = "sqc:monitor:task:running:";
    private static final int ALARM_EXPIRE_DAYS = 30;

    @Value("${sqc.monitor.check-interval:300}")
    private Integer checkIntervalSeconds;

    @Value("${sqc.monitor.alarm-threshold:3}")
    private Integer alarmThreshold;

    // ====================================================================
    //                         实时监控
    // ====================================================================

    /**
     * 实时检查质控数据是否失控
     */
    public MonitorAlarmDto checkQcResult(String planId, BigDecimal resultValue, LocalDateTime inspectTime) {
        log.info("实时检查质控结果, planId={}, value={}", planId, resultValue);

        SqcMovingPlan plan = sqcMovingPlanMapper.selectOneById(planId);
        if (plan == null || plan.getIsDeleted() == 1) {
            throw new SqcBusinessException(CommonErrorCode.PLAN_NOT_FOUND, "质控计划不存在");
        }

        if (plan.getPlanStatus() != 1) {
            log.debug("计划已禁用, 跳过检查, planId={}", planId);
            return null;
        }

        BigDecimal targetMean = plan.getTargetMean();
        BigDecimal targetSd = plan.getTargetSd();
        if (targetMean == null || targetSd == null || targetSd.compareTo(BigDecimal.ZERO) == 0) {
            log.warn("计划未设置靶值或标准差, planId={}", planId);
            return null;
        }

        // 计算Z-score
        BigDecimal zScore = resultValue.subtract(targetMean)
                .divide(targetSd, 4, RoundingMode.HALF_UP);
        BigDecimal absZScore = zScore.abs();

        MonitorAlarmDto alarm = new MonitorAlarmDto();
        alarm.setPlanId(planId);
        alarm.setItemCode(plan.getItemCode());
        alarm.setInstrumentCode(plan.getInstrumentCode());
        alarm.setResultValue(resultValue);
        alarm.setTargetMean(targetMean);
        alarm.setTargetSd(targetSd);
        alarm.setZScore(zScore);
        alarm.setInspectTime(inspectTime);
        alarm.setCheckTime(LocalDateTime.now());

        // 判定报警级别
        if (absZScore.compareTo(new BigDecimal("3")) > 0) {
            alarm.setAlarmLevel(AlarmLevelEnum.CRITICAL.getCode());
            alarm.setAlarmLevelName(AlarmLevelEnum.CRITICAL.getName());
            alarm.setRuleCode("1-3s");
            alarm.setRuleName("单值超过3个标准差");
            alarm.setAlarmMessage(String.format("质控失控(1-3s): %s, 结果值=%.4f, Z-score=%.2f",
                    plan.getItemCode(), resultValue, zScore));
        } else if (absZScore.compareTo(new BigDecimal("2")) > 0) {
            alarm.setAlarmLevel(AlarmLevelEnum.WARNING.getCode());
            alarm.setAlarmLevelName(AlarmLevelEnum.WARNING.getName());
            alarm.setRuleCode("1-2s");
            alarm.setRuleName("单值超过2个标准差");
            alarm.setAlarmMessage(String.format("质控警告(1-2s): %s, 结果值=%.4f, Z-score=%.2f",
                    plan.getItemCode(), resultValue, zScore));
        } else {
            alarm.setAlarmLevel(AlarmLevelEnum.NORMAL.getCode());
            alarm.setAlarmLevelName(AlarmLevelEnum.NORMAL.getName());
            alarm.setAlarmMessage("质控结果正常");
            return alarm;
        }

        // 保存报警记录
        saveAlarmRecord(alarm);

        // 发送报警通知
        sendAlarmNotification(alarm);

        return alarm;
    }

    /**
     * 批量生成报警
     */
    @Async("sqcTaskExecutor")
    public void generateAlarms(String planId, List<Map<String, Object>> ruleViolations) {
        if (CollectionUtils.isEmpty(ruleViolations)) {
            return;
        }

        log.info("批量生成报警, planId={}, violations={}", planId, ruleViolations.size());

        for (Map<String, Object> violation : ruleViolations) {
            try {
                MonitorAlarmDto alarm = new MonitorAlarmDto();
                alarm.setId(UUID.randomUUID().toString().replace("-", ""));
                alarm.setPlanId(planId);
                alarm.setRuleCode((String) violation.get("ruleCode"));
                alarm.setRuleName((String) violation.get("ruleName"));
                alarm.setAlarmLevel((String) violation.get("level"));
                alarm.setResultValue((BigDecimal) violation.get("value"));
                alarm.setAlarmTime(LocalDateTime.now());

                String level = (String) violation.get("level");
                AlarmLevelEnum alarmLevel = AlarmLevelEnum.fromCode(level);
                if (alarmLevel != null) {
                    alarm.setAlarmLevelName(alarmLevel.getName());
                }

                saveAlarmRecord(alarm);

                // 严重报警实时推送
                if ("CRITICAL".equals(level) || "ERROR".equals(level)) {
                    sendAlarmNotification(alarm);
                }
            } catch (Exception e) {
                log.error("生成报警失败, planId={}, violation={}", planId, violation, e);
            }
        }
    }

    // ====================================================================
    //                         监控仪表盘
    // ====================================================================

    /**
     * 获取监控仪表盘数据
     */
    public Map<String, Object> getDashboardData(String labCode, LocalDate date) {
        log.info("获取监控仪表盘数据, labCode={}, date={}", labCode, date);

        String cacheKey = MONITOR_CACHE_PREFIX + "dashboard:" + labCode + ":" + date;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached instanceof Map) {
            return (Map<String, Object>) cached;
        }

        Map<String, Object> dashboard = new LinkedHashMap<>();

        // 统计计划数
        QueryWrapper planQuery = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("is_deleted", 0);
        long totalPlans = sqcMovingPlanMapper.selectCountByQuery(planQuery);

        QueryWrapper activePlanQuery = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("plan_status", 1)
                .eq("is_deleted", 0);
        long activePlans = sqcMovingPlanMapper.selectCountByQuery(activePlanQuery);

        dashboard.put("totalPlans", totalPlans);
        dashboard.put("activePlans", activePlans);

        // 统计今日质控完成情况
        QueryWrapper todayCalcQuery = QueryWrapper.create()
                .eq("lab_code", labCode)
                .eq("plan_status", 1)
                .eq("is_deleted", 0)
                .ge("last_calc_time", date.atStartOfDay());
        long completedToday = sqcMovingPlanMapper.selectCountByQuery(todayCalcQuery);

        dashboard.put("completedToday", completedToday);
        dashboard.put("pendingToday", activePlans - completedToday);
        dashboard.put("completionRate", activePlans > 0 ?
                BigDecimal.valueOf(completedToday * 100.0 / activePlans)
                        .setScale(1, RoundingMode.HALF_UP) : BigDecimal.ZERO);

        // 统计今日报警
        Map<String, Integer> alarmStats = countAlarmsByLevel(labCode, date);
        dashboard.put("alarmStats", alarmStats);
        dashboard.put("totalAlarms", alarmStats.values().stream().mapToInt(Integer::intValue).sum());

        // 最近失控事件
        List<MonitorAlarmDto> recentAlarms = getRecentAlarms(labCode, 10);
        dashboard.put("recentAlarms", recentAlarms);

        dashboard.put("updateTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));

        // 缓存5分钟
        redisTemplate.opsForValue().set(cacheKey, dashboard, 300, TimeUnit.SECONDS);

        return dashboard;
    }

    /**
     * 按报警级别统计报警数
     */
    private Map<String, Integer> countAlarmsByLevel(String labCode, LocalDate date) {
        Map<String, Integer> stats = new LinkedHashMap<>();
        stats.put("CRITICAL", 0);
        stats.put("ERROR", 0);
        stats.put("WARNING", 0);

        // 从Redis中统计（简化实现）
        String alarmListKey = ALARM_CACHE_PREFIX + "list:" + labCode + ":" + date;
        List<Object> alarms = redisTemplate.opsForList().range(alarmListKey, 0, -1);
        if (alarms != null) {
            for (Object alarm : alarms) {
                if (alarm instanceof Map) {
                    String level = (String) ((Map<?, ?>) alarm).get("level");
                    stats.merge(level, 1, Integer::sum);
                }
            }
        }

        return stats;
    }

    /**
     * 获取最近的报警列表
     */
    public List<MonitorAlarmDto> getRecentAlarms(String labCode, int limit) {
        String cacheKey = ALARM_CACHE_PREFIX + "recent:" + labCode;
        List<Object> cached = redisTemplate.opsForList().range(cacheKey, 0, limit - 1);
        if (!CollectionUtils.isEmpty(cached)) {
            return cached.stream()
                    .filter(o -> o instanceof MonitorAlarmDto)
                    .map(o -> (MonitorAlarmDto) o)
                    .collect(Collectors.toList());
        }
        return Collections.emptyList();
    }

    // ====================================================================
    //                         任务管理
    // ====================================================================

    /**
     * 判断计划是否有正在运行的任务
     */
    public boolean hasRunningTask(String planId) {
        String key = TASK_RUNNING_KEY + planId;
        Object running = redisTemplate.opsForValue().get(key);
        return running != null && Boolean.TRUE.equals(running);
    }

    /**
     * 标记任务开始运行
     */
    public void markTaskRunning(String planId) {
        String key = TASK_RUNNING_KEY + planId;
        redisTemplate.opsForValue().set(key, Boolean.TRUE, 600, TimeUnit.SECONDS);
    }

    /**
     * 标记任务运行结束
     */
    public void markTaskCompleted(String planId) {
        String key = TASK_RUNNING_KEY + planId;
        redisTemplate.delete(key);
    }

    /**
     * 刷新计划配置（当计划被更新时调用）
     */
    public void refreshPlanConfig(String planId) {
        log.info("刷新计划监控配置, planId={}", planId);

        String configCacheKey = MONITOR_CACHE_PREFIX + "config:" + planId;
        redisTemplate.delete(configCacheKey);

        SqcMovingPlan plan = sqcMovingPlanMapper.selectOneById(planId);
        if (plan != null && plan.getIsDeleted() == 0 && plan.getPlanStatus() == 1) {
            Map<String, Object> config = new LinkedHashMap<>();
            config.put("planId", planId);
            config.put("algorithmCode", plan.getAlgorithmCode());
            config.put("movingWindow", plan.getMovingWindow());
            config.put("targetMean", plan.getTargetMean());
            config.put("targetSd", plan.getTargetSd());
            config.put("lastRefresh", LocalDateTime.now().toString());
            redisTemplate.opsForValue().set(configCacheKey, config, 3600, TimeUnit.SECONDS);
        }
    }

    /**
     * 统计最近N天的报警数
     */
    public int countRecentAlarms(String planId, int days) {
        String cacheKey = ALARM_CACHE_PREFIX + "count:" + planId + ":" + days;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached instanceof Integer) {
            return (Integer) cached;
        }

        // 从数据库统计（简化：直接返回缓存或0）
        int count = 0;
        redisTemplate.opsForValue().set(cacheKey, count, 600, TimeUnit.SECONDS);
        return count;
    }

    // ====================================================================
    //                         内部方法
    // ====================================================================

    /**
     * 保存报警记录
     */
    private void saveAlarmRecord(MonitorAlarmDto alarm) {
        try {
            if (alarm.getId() == null) {
                alarm.setId(UUID.randomUUID().toString().replace("-", ""));
            }
            alarm.setAlarmTime(LocalDateTime.now());

            // 保存到Redis列表
            String alarmKey = ALARM_CACHE_PREFIX + alarm.getPlanId();
            redisTemplate.opsForList().leftPush(alarmKey, alarm);
            redisTemplate.expire(alarmKey, ALARM_EXPIRE_DAYS, TimeUnit.DAYS);

            // 保存到最近报警列表
            String recentKey = ALARM_CACHE_PREFIX + "recent:" + alarm.getPlanId();
            redisTemplate.opsForList().leftPush(recentKey, alarm);
            redisTemplate.opsForList().trim(recentKey, 0, 99);

            log.info("报警记录保存成功, alarmId={}, level={}", alarm.getId(), alarm.getAlarmLevel());
        } catch (Exception e) {
            log.error("保存报警记录失败", e);
        }
    }

    /**
     * 发送报警通知
     */
    private void sendAlarmNotification(MonitorAlarmDto alarm) {
        try {
            Map<String, Object> notification = new LinkedHashMap<>();
            notification.put("type", "QC_ALARM");
            notification.put("alarmId", alarm.getId());
            notification.put("planId", alarm.getPlanId());
            notification.put("level", alarm.getAlarmLevel());
            notification.put("message", alarm.getAlarmMessage());
            notification.put("timestamp", System.currentTimeMillis());

            redisQueueService.sendMessage("sqc:notification:alarm", notification);
            log.info("报警通知已发送, alarmId={}", alarm.getId());
        } catch (Exception e) {
            log.error("发送报警通知失败, alarmId={}", alarm.getId(), e);
        }
    }

    /**
     * 构建监控任务BO
     */
    public MonitorTaskBo buildMonitorTask(String planId, String taskType) {
        SqcMovingPlan plan = sqcMovingPlanMapper.selectOneById(planId);
        if (plan == null) {
            return null;
        }

        MonitorTaskBo taskBo = new MonitorTaskBo();
        taskBo.setTaskId(UUID.randomUUID().toString().replace("-", ""));
        taskBo.setPlanId(planId);
        taskBo.setLabCode(plan.getLabCode());
        taskBo.setInstrumentCode(plan.getInstrumentCode());
        taskBo.setItemCode(plan.getItemCode());
        taskBo.setTaskType(taskType);
        taskBo.setTaskStatus(MonitorStatusEnum.PENDING.getCode());
        taskBo.setCreateTime(LocalDateTime.now());

        return taskBo;
    }
}
