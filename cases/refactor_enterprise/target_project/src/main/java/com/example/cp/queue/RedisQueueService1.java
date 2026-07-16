package com.example.cp.queue;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * Redis消息队列服务（新版）
 * <p>
 * 基于Redis List实现的简易消息队列，替换旧版RedisQueueService。
 * 新增特性：
 * - 消息优先级支持
 * - 消息TTL支持
 * - 消费者组支持（简化版）
 * </p>
 *
 * @author cp-team
 * @since 2024-02-15
 */
@Component
public class RedisQueueService1 {

    private static final Logger log = LoggerFactory.getLogger(RedisQueueService1.class);

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${cp.queue.max-retry:3}")
    private Integer maxRetry;

    @Value("${cp.queue.timeout:5000}")
    private Long queueTimeout;

    @Value("${cp.queue.consumer-group:default}")
    private String defaultConsumerGroup;

    private static final String QUEUE_PREFIX = "cp:queue:";
    private static final String DLQ_PREFIX = "cp:dlq:";
    private static final String PROCESSING_PREFIX = "cp:processing:";
    private static final String PRIORITY_PREFIX = "cp:priority:";

    // ====================================================================
    //                         发送消息
    // ====================================================================

    /**
     * 发送消息到队列
     *
     * @param queueName 队列名称
     * @param message   消息对象
     */
    public void sendMessage(String queueName, Object message) {
        if (!StringUtils.hasText(queueName)) {
            log.error("队列名称不能为空");
            return;
        }
        if (message == null) {
            log.error("消息不能为空");
            return;
        }

        String fullQueueName = QUEUE_PREFIX + queueName;
        try {
            Map<String, Object> envelope = new LinkedHashMap<>();
            envelope.put("messageId", UUID.randomUUID().toString().replace("-", ""));
            envelope.put("queueName", queueName);
            envelope.put("payload", message);
            envelope.put("timestamp", System.currentTimeMillis());
            envelope.put("sendTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
            envelope.put("retryCount", 0);
            envelope.put("priority", "NORMAL");
            envelope.put("consumerGroup", defaultConsumerGroup);

            redisTemplate.opsForList().rightPush(fullQueueName, envelope);
            log.debug("消息发送成功, queue={}, messageId={}", queueName, envelope.get("messageId"));
        } catch (Exception e) {
            log.error("发送消息失败, queue={}", queueName, e);
            throw new RuntimeException("发送消息失败: " + e.getMessage(), e);
        }
    }

    /**
     * 发送高优先级消息
     *
     * @param queueName 队列名称
     * @param message   消息对象
     */
    public void sendHighPriorityMessage(String queueName, Object message) {
        if (!StringUtils.hasText(queueName)) {
            log.error("队列名称不能为空");
            return;
        }

        String fullQueueName = QUEUE_PREFIX + queueName;
        try {
            Map<String, Object> envelope = new LinkedHashMap<>();
            envelope.put("messageId", UUID.randomUUID().toString().replace("-", ""));
            envelope.put("queueName", queueName);
            envelope.put("payload", message);
            envelope.put("timestamp", System.currentTimeMillis());
            envelope.put("sendTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
            envelope.put("retryCount", 0);
            envelope.put("priority", "HIGH");
            envelope.put("consumerGroup", defaultConsumerGroup);

            // 高优先级消息插入队头
            redisTemplate.opsForList().leftPush(fullQueueName, envelope);
            log.debug("高优先级消息发送成功, queue={}, messageId={}", queueName, envelope.get("messageId"));
        } catch (Exception e) {
            log.error("发送高优先级消息失败, queue={}", queueName, e);
            throw new RuntimeException("发送消息失败: " + e.getMessage(), e);
        }
    }

    /**
     * 发送延迟消息
     *
     * @param queueName    队列名称
     * @param message      消息对象
     * @param delaySeconds 延迟秒数
     */
    public void sendDelayMessage(String queueName, Object message, long delaySeconds) {
        if (!StringUtils.hasText(queueName)) {
            log.error("队列名称不能为空");
            return;
        }

        String delayQueueName = QUEUE_PREFIX + "delay:" + queueName;
        try {
            Map<String, Object> envelope = new LinkedHashMap<>();
            envelope.put("messageId", UUID.randomUUID().toString().replace("-", ""));
            envelope.put("queueName", queueName);
            envelope.put("payload", message);
            envelope.put("timestamp", System.currentTimeMillis());
            envelope.put("executeTime", System.currentTimeMillis() + delaySeconds * 1000);
            envelope.put("retryCount", 0);
            envelope.put("priority", "NORMAL");
            envelope.put("consumerGroup", defaultConsumerGroup);

            // 使用ZSet实现延迟队列
            double score = System.currentTimeMillis() + delaySeconds * 1000.0;
            String messageJson = objectMapper.writeValueAsString(envelope);
            stringRedisTemplate.opsForZSet().add(delayQueueName, messageJson, score);

            log.debug("延迟消息发送成功, queue={}, delay={}s", queueName, delaySeconds);
        } catch (JsonProcessingException e) {
            log.error("序列化消息失败, queue={}", queueName, e);
        } catch (Exception e) {
            log.error("发送延迟消息失败, queue={}", queueName, e);
        }
    }

    /**
     * 批量发送消息
     */
    public void sendBatchMessages(String queueName, List<Object> messages) {
        if (!StringUtils.hasText(queueName) || messages == null || messages.isEmpty()) {
            return;
        }

        String fullQueueName = QUEUE_PREFIX + queueName;
        try {
            for (Object message : messages) {
                Map<String, Object> envelope = new LinkedHashMap<>();
                envelope.put("messageId", UUID.randomUUID().toString().replace("-", ""));
                envelope.put("queueName", queueName);
                envelope.put("payload", message);
                envelope.put("timestamp", System.currentTimeMillis());
                envelope.put("retryCount", 0);
                envelope.put("priority", "NORMAL");
                envelope.put("consumerGroup", defaultConsumerGroup);

                redisTemplate.opsForList().rightPush(fullQueueName, envelope);
            }
            log.info("批量消息发送成功, queue={}, count={}", queueName, messages.size());
        } catch (Exception e) {
            log.error("批量发送消息失败, queue={}", queueName, e);
        }
    }

    // ====================================================================
    //                         消费消息
    // ====================================================================

    /**
     * 消费消息（阻塞式）
     */
    public Object consumeMessage(String queueName) {
        String fullQueueName = QUEUE_PREFIX + queueName;
        String processingName = PROCESSING_PREFIX + queueName;

        try {
            Object message = redisTemplate.opsForList().rightPopAndLeftPush(
                    fullQueueName, processingName, queueTimeout, TimeUnit.MILLISECONDS);

            if (message != null) {
                log.debug("消费消息成功, queue={}", queueName);
            }
            return message;
        } catch (Exception e) {
            log.error("消费消息失败, queue={}", queueName, e);
            return null;
        }
    }

    /**
     * 消费消息（指定消费者组）
     */
    public Object consumeMessage(String queueName, String consumerGroup) {
        String fullQueueName = QUEUE_PREFIX + queueName + ":" + consumerGroup;
        String processingName = PROCESSING_PREFIX + queueName + ":" + consumerGroup;

        try {
            Object message = redisTemplate.opsForList().rightPopAndLeftPush(
                    fullQueueName, processingName, queueTimeout, TimeUnit.MILLISECONDS);

            if (message != null) {
                log.debug("消费消息成功, queue={}, group={}", queueName, consumerGroup);
            }
            return message;
        } catch (Exception e) {
            log.error("消费消息失败, queue={}, group={}", queueName, consumerGroup, e);
            return null;
        }
    }

    /**
     * 确认消息消费完成
     */
    public void ackMessage(String queueName, Object message) {
        String processingName = PROCESSING_PREFIX + queueName;
        try {
            redisTemplate.opsForList().remove(processingName, 1, message);
            log.debug("消息确认成功, queue={}", queueName);
        } catch (Exception e) {
            log.error("消息确认失败, queue={}", queueName, e);
        }
    }

    /**
     * 消息消费失败，重试或进入死信队列
     */
    public void nackMessage(String queueName, Object message) {
        String processingName = PROCESSING_PREFIX + queueName;
        String dlqName = DLQ_PREFIX + queueName;

        try {
            if (message instanceof Map) {
                Map<String, Object> envelope = (Map<String, Object>) message;
                int retryCount = (int) envelope.getOrDefault("retryCount", 0);

                if (retryCount < maxRetry) {
                    envelope.put("retryCount", retryCount + 1);
                    envelope.put("lastRetryTime", LocalDateTime.now().format(
                            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
                    envelope.put("retryReason", "消费失败自动重试");

                    // 重新入队
                    String fullQueueName = QUEUE_PREFIX + queueName;
                    redisTemplate.opsForList().rightPush(fullQueueName, envelope);
                    log.info("消息重试入队, queue={}, retryCount={}", queueName, retryCount + 1);
                } else {
                    // 进入死信队列
                    envelope.put("deadLetterTime", LocalDateTime.now().format(
                            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
                    envelope.put("deadLetterReason", "超过最大重试次数: " + maxRetry);
                    redisTemplate.opsForList().rightPush(dlqName, envelope);
                    log.warn("消息进入死信队列, queue={}, maxRetry={}", queueName, maxRetry);
                }
            }

            // 从处理中队列移除
            redisTemplate.opsForList().remove(processingName, 1, message);
        } catch (Exception e) {
            log.error("处理消息失败, queue={}", queueName, e);
        }
    }

    // ====================================================================
    //                         队列管理
    // ====================================================================

    /**
     * 获取队列长度
     */
    public long getQueueSize(String queueName) {
        String fullQueueName = QUEUE_PREFIX + queueName;
        Long size = redisTemplate.opsForList().size(fullQueueName);
        return size != null ? size : 0;
    }

    /**
     * 获取处理中队列长度
     */
    public long getProcessingQueueSize(String queueName) {
        String processingName = PROCESSING_PREFIX + queueName;
        Long size = redisTemplate.opsForList().size(processingName);
        return size != null ? size : 0;
    }

    /**
     * 获取死信队列长度
     */
    public long getDeadLetterQueueSize(String queueName) {
        String dlqName = DLQ_PREFIX + queueName;
        Long size = redisTemplate.opsForList().size(dlqName);
        return size != null ? size : 0;
    }

    /**
     * 清空队列
     */
    public void clearQueue(String queueName) {
        String fullQueueName = QUEUE_PREFIX + queueName;
        redisTemplate.delete(fullQueueName);
        log.info("队列已清空, queue={}", queueName);
    }

    /**
     * 查看队列中的消息（不消费）
     */
    public List<Object> peekMessages(String queueName, int count) {
        String fullQueueName = QUEUE_PREFIX + queueName;
        return redisTemplate.opsForList().range(fullQueueName, 0, count - 1);
    }

    /**
     * 重新处理死信队列消息
     */
    public int reprocessDeadLetterQueue(String queueName, int maxCount) {
        String dlqName = DLQ_PREFIX + queueName;
        String fullQueueName = QUEUE_PREFIX + queueName;

        int count = 0;
        for (int i = 0; i < maxCount; i++) {
            Object message = redisTemplate.opsForList().rightPop(dlqName);
            if (message == null) {
                break;
            }

            if (message instanceof Map) {
                Map<String, Object> envelope = (Map<String, Object>) message;
                envelope.put("retryCount", 0);
                envelope.put("reprocessTime", LocalDateTime.now().format(
                        DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
                redisTemplate.opsForList().rightPush(fullQueueName, envelope);
                count++;
            }
        }

        log.info("死信队列重处理完成, queue={}, count={}", queueName, count);
        return count;
    }

    /**
     * 获取队列统计信息
     */
    public Map<String, Object> getQueueStats(String queueName) {
        Map<String, Object> stats = new LinkedHashMap<>();
        stats.put("queueName", queueName);
        stats.put("pendingSize", getQueueSize(queueName));
        stats.put("processingSize", getProcessingQueueSize(queueName));
        stats.put("deadLetterSize", getDeadLetterQueueSize(queueName));
        stats.put("queryTime", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        return stats;
    }
}
