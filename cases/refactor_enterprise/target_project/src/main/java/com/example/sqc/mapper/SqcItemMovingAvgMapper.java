package com.example.sqc.mapper;

import com.example.sqc.model.SqcItemMovingAvg;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDate;
import java.util.List;

/**
 * 质控项目移动均值Mapper
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Mapper
public interface SqcItemMovingAvgMapper extends BaseMapper<SqcItemMovingAvg> {

    @Select("SELECT * FROM sqc_item_moving_avg " +
            "WHERE plan_id = #{planId} " +
            "AND calc_date BETWEEN #{startDate} AND #{endDate} " +
            "ORDER BY calc_date ASC")
    List<SqcItemMovingAvg> findByPlanAndDateRange(
            @Param("planId") String planId,
            @Param("startDate") LocalDate startDate,
            @Param("endDate") LocalDate endDate);

    @Select("SELECT * FROM sqc_item_moving_avg " +
            "WHERE plan_id = #{planId} " +
            "ORDER BY calc_date DESC " +
            "LIMIT 1")
    SqcItemMovingAvg findLatestByPlan(@Param("planId") String planId);

    @Select("SELECT item_code, AVG(avg_mean) as mean, AVG(avg_sd) as sd " +
            "FROM sqc_item_moving_avg " +
            "WHERE instrument_code = #{instrumentCode} " +
            "AND calc_date >= #{startDate} " +
            "GROUP BY item_code")
    List<java.util.Map<String, Object>> summaryByInstrument(
            @Param("instrumentCode") String instrumentCode,
            @Param("startDate") LocalDate startDate);
}
