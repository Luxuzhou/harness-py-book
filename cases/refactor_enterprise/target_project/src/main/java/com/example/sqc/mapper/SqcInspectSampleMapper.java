package com.example.sqc.mapper;

import com.example.sqc.model.SqcInspectSample;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 质控检验样本Mapper
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Mapper
public interface SqcInspectSampleMapper extends BaseMapper<SqcInspectSample> {

    @Select("SELECT * FROM sqc_inspect_sample " +
            "WHERE plan_id = #{planId} " +
            "AND inspect_time BETWEEN #{startTime} AND #{endTime} " +
            "AND is_deleted = 0 " +
            "ORDER BY inspect_time DESC")
    List<SqcInspectSample> findByPlanAndTimeRange(
            @Param("planId") String planId,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    @Select("SELECT COUNT(*) FROM sqc_inspect_sample " +
            "WHERE plan_id = #{planId} AND is_deleted = 0")
    long countByPlan(@Param("planId") String planId);

    @Select("SELECT * FROM sqc_inspect_sample " +
            "WHERE plan_id = #{planId} AND is_deleted = 0 " +
            "ORDER BY inspect_time DESC LIMIT #{limit}")
    List<SqcInspectSample> findRecentSamples(
            @Param("planId") String planId,
            @Param("limit") int limit);
}
