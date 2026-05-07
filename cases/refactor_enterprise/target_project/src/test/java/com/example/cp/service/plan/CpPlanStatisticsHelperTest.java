package com.example.cp.service.plan;

import com.example.cp.service.plan.support.CpPlanStatisticsHelper;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * CpPlanStatisticsHelper 单元测试
 */
class CpPlanStatisticsHelperTest {

    @Test
    void testCalculateMovingAverage_normal() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("1"), new BigDecimal("2"), new BigDecimal("3"),
                new BigDecimal("4"), new BigDecimal("5"));
        List<BigDecimal> result = CpPlanStatisticsHelper.calculateMovingAverage(values, 3);
        assertEquals(3, result.size());
        assertEquals(new BigDecimal("2.000000"), result.get(0));
        assertEquals(new BigDecimal("3.000000"), result.get(1));
        assertEquals(new BigDecimal("4.000000"), result.get(2));
    }

    @Test
    void testCalculateMovingAverage_insufficientData() {
        List<BigDecimal> values = Arrays.asList(new BigDecimal("1"), new BigDecimal("2"));
        List<BigDecimal> result = CpPlanStatisticsHelper.calculateMovingAverage(values, 3);
        assertEquals(2, result.size());
    }

    @Test
    void testCalculateMovingAverage_emptyInput() {
        List<BigDecimal> result = CpPlanStatisticsHelper.calculateMovingAverage(Collections.emptyList(), 3);
        assertTrue(result.isEmpty());
    }

    @Test
    void testCalculateMean_normal() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("1"), new BigDecimal("2"), new BigDecimal("3"));
        BigDecimal mean = CpPlanStatisticsHelper.calculateMean(values);
        assertEquals(new BigDecimal("2.000000"), mean);
    }

    @Test
    void testCalculateMean_emptyInput() {
        assertEquals(BigDecimal.ZERO, CpPlanStatisticsHelper.calculateMean(Collections.emptyList()));
    }

    @Test
    void testCalculateStandardDeviation_normal() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("1"), new BigDecimal("2"), new BigDecimal("3"));
        BigDecimal mean = CpPlanStatisticsHelper.calculateMean(values);
        BigDecimal sd = CpPlanStatisticsHelper.calculateStandardDeviation(values, mean);
        assertTrue(sd.compareTo(BigDecimal.ZERO) > 0);
        assertEquals(new BigDecimal("1.000000"), sd.setScale(6, RoundingMode.HALF_UP));
    }

    @Test
    void testCalculateStandardDeviation_insufficientData() {
        List<BigDecimal> values = Collections.singletonList(new BigDecimal("1"));
        BigDecimal sd = CpPlanStatisticsHelper.calculateStandardDeviation(values, new BigDecimal("1"));
        assertEquals(BigDecimal.ZERO, sd);
    }

    @Test
    void testSqrt_positive() {
        BigDecimal result = CpPlanStatisticsHelper.sqrt(new BigDecimal("4"), 6);
        assertEquals(new BigDecimal("2.000000"), result);
    }

    @Test
    void testSqrt_zero() {
        assertEquals(BigDecimal.ZERO, CpPlanStatisticsHelper.sqrt(BigDecimal.ZERO, 6));
    }

    @Test
    void testApplyNormalTransform_log() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("1"), new BigDecimal("10"), new BigDecimal("100"));
        List<BigDecimal> result = CpPlanStatisticsHelper.applyNormalTransform(values, "LOG");
        assertEquals(3, result.size());
        assertTrue(result.get(0).compareTo(BigDecimal.ZERO) >= 0);
    }

    @Test
    void testApplyNormalTransform_sqrt() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("4"), new BigDecimal("9"), new BigDecimal("16"));
        List<BigDecimal> result = CpPlanStatisticsHelper.applyNormalTransform(values, "SQRT");
        assertEquals(3, result.size());
        assertEquals(new BigDecimal("2.000000"), result.get(0));
        assertEquals(new BigDecimal("3.000000"), result.get(1));
        assertEquals(new BigDecimal("4.000000"), result.get(2));
    }

    @Test
    void testApplyWestgardRules_noViolations() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("100"), new BigDecimal("101"), new BigDecimal("99"));
        List<Map<String, Object>> violations = CpPlanStatisticsHelper.applyWestgardRules(
                values, new BigDecimal("100"), new BigDecimal("1"));
        assertTrue(violations.isEmpty());
    }

    @Test
    void testApplyWestgardRules_1s3sViolation() {
        List<BigDecimal> values = Arrays.asList(
                new BigDecimal("100"), new BigDecimal("104"), new BigDecimal("100"));
        List<Map<String, Object>> violations = CpPlanStatisticsHelper.applyWestgardRules(
                values, new BigDecimal("100"), new BigDecimal("1"));
        assertFalse(violations.isEmpty());
        assertEquals("1-3s", violations.get(0).get("ruleCode"));
    }

    @Test
    void testApplyWestgardRules_emptyInput() {
        List<Map<String, Object>> violations = CpPlanStatisticsHelper.applyWestgardRules(
                Collections.emptyList(), new BigDecimal("100"), new BigDecimal("1"));
        assertTrue(violations.isEmpty());
    }
}
