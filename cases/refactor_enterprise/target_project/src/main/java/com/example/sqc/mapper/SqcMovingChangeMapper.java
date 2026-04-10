package com.example.sqc.mapper;

import com.example.sqc.model.SqcMovingChange;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 质控计划变更记录Mapper
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Mapper
public interface SqcMovingChangeMapper extends BaseMapper<SqcMovingChange> {

    @Select("SELECT * FROM sqc_moving_change " +
            "WHERE plan_id = #{planId} " +
            "ORDER BY change_time DESC " +
            "LIMIT #{limit}")
    List<SqcMovingChange> findRecentChanges(
            @Param("planId") String planId,
            @Param("limit") int limit);

    @Select("SELECT * FROM sqc_moving_change " +
            "WHERE plan_id = #{planId} " +
            "AND change_time BETWEEN #{startTime} AND #{endTime} " +
            "ORDER BY change_time DESC")
    List<SqcMovingChange> findChangesByTimeRange(
            @Param("planId") String planId,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    @Select("SELECT field_name, COUNT(*) as change_count " +
            "FROM sqc_moving_change " +
            "WHERE plan_id = #{planId} " +
            "GROUP BY field_name " +
            "ORDER BY change_count DESC")
    List<java.util.Map<String, Object>> countChangesByField(@Param("planId") String planId);
}
