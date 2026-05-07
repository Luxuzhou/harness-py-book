package com.example.cp.service.plan;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * CpPlanCacheService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class CpPlanCacheServiceTest {

    @Mock
    private RedisTemplate<String, Object> redisTemplate;
    @Mock
    private ValueOperations<String, Object> valueOperations;

    private CpPlanCacheService cpPlanCacheService;

    @BeforeEach
    void setUp() {
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        cpPlanCacheService = new CpPlanCacheService(redisTemplate);
    }

    @Test
    void testGet_fromCache() {
        String expected = "cached-value";
        when(valueOperations.get("cp:plan:test-key")).thenReturn(expected);

        String result = cpPlanCacheService.get("test-key");
        assertEquals(expected, result);
    }

    @Test
    void testGet_cacheMiss() {
        when(valueOperations.get("cp:plan:missing-key")).thenReturn(null);

        String result = cpPlanCacheService.get("missing-key");
        assertNull(result);
    }

    @Test
    void testSet_success() {
        cpPlanCacheService.set("test-key", "value", 3600L);
        verify(valueOperations).set("cp:plan:test-key", "value", 3600L, java.util.concurrent.TimeUnit.SECONDS);
    }

    @Test
    void testDelete_success() {
        cpPlanCacheService.delete("test-key");
        verify(redisTemplate).delete("cp:plan:test-key");
    }

    @Test
    void testClearPlanListCache_success() {
        cpPlanCacheService.clearPlanListCache("LAB001", "INS001");
        verify(redisTemplate).delete("cp:plan:list:LAB001:INS001");
    }

    @Test
    void testClearPlanListCache_redisError() {
        doThrow(new RuntimeException("Redis error")).when(redisTemplate).delete(anyString());
        // Should not throw
        cpPlanCacheService.clearPlanListCache("LAB001", "INS001");
    }

    @Test
    void testClearPlanCache_success() {
        cpPlanCacheService.clearPlanCache("plan-1");
        verify(redisTemplate).delete("cp:plan:plan-1");
    }
}
