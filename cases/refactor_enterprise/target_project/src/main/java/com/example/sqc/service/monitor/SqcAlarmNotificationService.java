package com.example.sqc.service.monitor;

import com.example.sqc.dto.monitor.MonitorAlarmDto;
import com.example.sqc.enums.monitor.AlarmLevelEnum;
import com.example.sqc.queue.RedisQueueService1;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * 质控报警通知服务
 * <p>
 * 负责将质控报警通过各种渠道发送给相关人员：
 * - 系统内消息推送（WebSocket）
 * - 企业微信/钉钉消息
 * - 短信通知（严重报警）
 * - 邮件通知（日报/周报）
 * </p>
 *
 * @author sqc-team
 * @since 2024-03-25
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SqcAlarmNotificationService {

    private final RedisTemplate<String, Object> redisTemplate;
    private final RedisQueueService1 redisQueueService;

    private static final String NOTIFICATION_QUEUE = "sqc:notification:alarm";
    private static final String NOTIFICATION_LOG_PREFIX = "sqc:notification:log:";
    private static final String NOTIFICATION_RATE_LIMIT_PREFIX = "sqc:notification:rate:";

    // 硬编码的通知配置（坏味道：应该配置化）
    private static final String WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx-yyyy-zzzz";
    private static final String SMS_API_URL = "http://192.168.1.200:8090/api/sms/send";
    private static final String EMAIL_SMTP_HOST = "smtp.example.com";
    private static final int MAX_NOTIFICATIONS_PER_HOUR = 50;

    @Value("${sqc.notification.enabled:true}")
    private Boolean notificationEnabled;

    @Value("${sqc.notification.sms.enabled:false}")
    private Boolean smsEnabled;

    @Value("${sqc.notification.wechat.enabled:true}")
    private Boolean wechatEnabled;

    /**
     * 发送报警通知
     */
    @Async("sqcTaskExecutor")
    public void sendAlarmNotification(MonitorAlarmDto alarm) {
        if (!Boolean.TRUE.equals(notificationEnabled)) {
            return;
        }

        if (alarm == null || !StringUtils.hasText(alarm.getAlarmLevel())) {
            return;
        }

        // 频率限制检查
        if (isRateLimited(alarm.getPlanId())) {
            log.debug("报警通知被限流, planId={}", alarm.getPlanId());
            return;
        }

        try {
            AlarmLevelEnum level = AlarmLevelEnum.fromCode(alarm.getAlarmLevel());
            if (level == null) {
                return;
            }

            // 根据报警级别选择通知渠道
            switch (level) {
                case CRITICAL:
                    // 严重报警：所有渠道都通知
                    sendSystemNotification(alarm);
                    if (Boolean.TRUE.equals(wechatEnabled)) {
                        sendWechatNotification(alarm);
                    }
                    if (Boolean.TRUE.equals(smsEnabled)) {
                        sendSmsNotification(alarm);
                    }
                    break;
                case ERROR:
                    // 异常：系统通知 + 企微通知
                    sendSystemNotification(alarm);
                    if (Boolean.TRUE.equals(wechatEnabled)) {
                        sendWechatNotification(alarm);
                    }
                    break;
                case WARNING:
                    // 警告：仅系统通知
                    sendSystemNotification(alarm);
                    break;
                default:
                    break;
            }

            // 记录通知日志
            recordNotificationLog(alarm);

        } catch (Exception e) {
            log.error("发送报警通知失败, alarmId={}", alarm.getId(), e);
        }
    }

    /**
     * 批量发送报警通知
     */
    @Async("sqcTaskExecutor")
    public void sendBatchNotifications(List<MonitorAlarmDto> alarms) {
        if (CollectionUtils.isEmpty(alarms)) {
            return;
        }

        // 按级别分组
        Map<String, List<MonitorAlarmDto>> grouped = alarms.stream()
                .filter(a -> a.getAlarmLevel() != null)
                .collect(Collectors.groupingBy(MonitorAlarmDto::getAlarmLevel));

        // 严重和异常报警逐条发送
        List<MonitorAlarmDto> criticalAlarms = grouped.getOrDefault("CRITICAL", Collections.emptyList());
        List<MonitorAlarmDto> errorAlarms = grouped.getOrDefault("ERROR", Collections.emptyList());

        for (MonitorAlarmDto alarm : criticalAlarms) {
            sendAlarmNotification(alarm);
        }
        for (MonitorAlarmDto alarm : errorAlarms) {
            sendAlarmNotification(alarm);
        }

        // 警告报警汇总发送
        List<MonitorAlarmDto> warningAlarms = grouped.getOrDefault("WARNING", Collections.emptyList());
        if (!warningAlarms.isEmpty()) {
            sendWarningDigest(warningAlarms);
        }
    }

    /**
     * 发送系统内通知
     */
    private void sendSystemNotification(MonitorAlarmDto alarm) {
        try {
            Map<String, Object> notification = new LinkedHashMap<>();
            notification.put("type", "SYSTEM");
            notification.put("alarmId", alarm.getId());
            notification.put("planId", alarm.getPlanId());
            notification.put("level", alarm.getAlarmLevel());
            notification.put("title", "质控报警: " + alarm.getRuleName());
            notification.put("content", alarm.getAlarmMessage());
            notification.put("timestamp", System.currentTimeMillis());

            redisQueueService.sendMessage("sqc:notification:system", notification);
            log.debug("系统通知已发送, alarmId={}", alarm.getId());
        } catch (Exception e) {
            log.error("发送系统通知失败, alarmId={}", alarm.getId(), e);
        }
    }

    /**
     * 发送企业微信通知
     */
    private void sendWechatNotification(MonitorAlarmDto alarm) {
        try {
            // 构建企微消息体
            Map<String, Object> message = new LinkedHashMap<>();
            message.put("msgtype", "markdown");

            Map<String, String> markdown = new LinkedHashMap<>();
            StringBuilder content = new StringBuilder();
            content.append("### 质控报警通知\n");
            content.append("> **级别**: <font color=\"warning\">").append(alarm.getAlarmLevelName()).append("</font>\n");
            content.append("> **项目**: ").append(alarm.getItemCode()).append("\n");
            content.append("> **仪器**: ").append(alarm.getInstrumentCode()).append("\n");
            content.append("> **规则**: ").append(alarm.getRuleName()).append("\n");
            content.append("> **详情**: ").append(alarm.getAlarmMessage()).append("\n");
            content.append("> **时间**: ").append(LocalDateTime.now().format(
                    DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"))).append("\n");

            markdown.put("content", content.toString());
            message.put("markdown", markdown);

            // 实际发送：通过HTTP POST到企微Webhook
            // TODO: 使用RestTemplate发送
            log.info("企微通知已构建, alarmId={}", alarm.getId());
        } catch (Exception e) {
            log.error("发送企微通知失败, alarmId={}", alarm.getId(), e);
        }
    }

    /**
     * 发送短信通知
     */
    private void sendSmsNotification(MonitorAlarmDto alarm) {
        try {
            Map<String, Object> smsRequest = new LinkedHashMap<>();
            smsRequest.put("phone", ""); // 从配置获取值班人手机号
            smsRequest.put("template", "SQC_ALARM");
            smsRequest.put("params", Map.of(
                    "level", alarm.getAlarmLevelName(),
                    "item", alarm.getItemCode(),
                    "rule", alarm.getRuleName()
            ));

            // TODO: 通过HTTP POST到短信接口
            log.info("短信通知已构建, alarmId={}", alarm.getId());
        } catch (Exception e) {
            log.error("发送短信通知失败, alarmId={}", alarm.getId(), e);
        }
    }

    /**
     * 发送警告汇总
     */
    private void sendWarningDigest(List<MonitorAlarmDto> warnings) {
        try {
            Map<String, Object> digest = new LinkedHashMap<>();
            digest.put("type", "WARNING_DIGEST");
            digest.put("count", warnings.size());
            digest.put("items", warnings.stream()
                    .map(w -> Map.of(
                            "itemCode", w.getItemCode() != null ? w.getItemCode() : "",
                            "rule", w.getRuleName() != null ? w.getRuleName() : ""
                    ))
                    .collect(Collectors.toList()));
            digest.put("timestamp", System.currentTimeMillis());

            redisQueueService.sendMessage("sqc:notification:digest", digest);
            log.info("警告汇总通知已发送, count={}", warnings.size());
        } catch (Exception e) {
            log.error("发送警告汇总失败", e);
        }
    }

    /**
     * 频率限制检查
     */
    private boolean isRateLimited(String planId) {
        String key = NOTIFICATION_RATE_LIMIT_PREFIX + planId + ":" +
                LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHH"));
        Long count = redisTemplate.opsForValue().increment(key, 1);
        if (count != null && count == 1) {
            redisTemplate.expire(key, 1, TimeUnit.HOURS);
        }
        return count != null && count > MAX_NOTIFICATIONS_PER_HOUR;
    }

    /**
     * 记录通知日志
     */
    private void recordNotificationLog(MonitorAlarmDto alarm) {
        try {
            String logKey = NOTIFICATION_LOG_PREFIX + LocalDate.now();
            Map<String, Object> logEntry = new LinkedHashMap<>();
            logEntry.put("alarmId", alarm.getId());
            logEntry.put("planId", alarm.getPlanId());
            logEntry.put("level", alarm.getAlarmLevel());
            logEntry.put("notifyTime", LocalDateTime.now().toString());

            redisTemplate.opsForList().leftPush(logKey, logEntry);
            redisTemplate.expire(logKey, 30, TimeUnit.DAYS);
        } catch (Exception e) {
            log.warn("记录通知日志失败", e);
        }
    }
}
