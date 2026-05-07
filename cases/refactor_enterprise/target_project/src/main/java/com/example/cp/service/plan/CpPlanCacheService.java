package com.example.cp.service.plan;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.util.concurrent.TimeUnit;

/**
 * 临床路径方案缓存管理服务
 * <p>
 * 负责临床路径方案相关的Redis缓存读写与清理。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-15
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CpPlanCacheService {

    private final RedisTemplate<String, Object> redisTemplate;

    private static final String PLAN_CACHE_PREFIX = "cp:plan:";

    /**
     * 从缓存获取对象
     */
    @SuppressWarnings("unchecked")
    public <T> T get(String keySuffix) {
        String cacheKey = PLAN_CACHE_PREFIX + keySuffix;
        Object cached = redisTemplate.opsForValue().get(cacheKey);
        if (cached != null) {
            return (T) cached;
        }
        return null;
    }

    /**
     * 写入缓存
     */
    public void set(String keySuffix, Object value, long ttlSeconds) {
        String cacheKey = PLAN_CACHE_PREFIX + keySuffix;
        redisTemplate.opsForValue().set(cacheKey, value, ttlSeconds, TimeUnit.SECONDS);
    }

    /**
     * 删除指定缓存
     */
    public void delete(String keySuffix) {
        String cacheKey = PLAN_CACHE_PREFIX + keySuffix;
        redisTemplate.delete(cacheKey);
    }

    /**
     * 清除计划列表缓存
     */
    public void clearPlanListCache(String labCode, String instrumentCode) {
        try {
            String listCacheKey = PLAN_CACHE_PREFIX + "list:" + labCode + ":" + instrumentCode;
            redisTemplate.delete(listCacheKey);
        } catch (Exception e) {
            log.warn("清除计划列表缓存失败, labCode={}, instrumentCode={}", labCode, instrumentCode, e);
        }
    }

    /**
     * 清除单个计划缓存
     */
    public void clearPlanCache(String planId) {
        try {
            redisTemplate.delete(PLAN_CACHE_PREFIX + planId);
        } catch (Exception e) {
            log.warn("清除计划缓存失败, planId={}", planId, e);
        }
    }
}
