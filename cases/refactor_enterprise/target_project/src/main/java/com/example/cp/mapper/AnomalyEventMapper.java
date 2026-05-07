package com.example.cp.mapper;

import com.example.cp.model.AnomalyEvent;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 异常事件 Mapper
 * <p>
 * 提供对 anomaly_event 表的基础 CRUD 操作及自定义查询。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
@Mapper
public interface AnomalyEventMapper extends BaseMapper<AnomalyEvent> {

    /**
     * 按诊疗项目ID查询异常事件，按触发时间降序排列
     *
     * @param testItemId 诊疗项目ID
     * @return 异常事件列表
     */
    @Select("SELECT * FROM anomaly_event WHERE test_item_id = #{testItemId} ORDER BY triggered_at DESC")
    List<AnomalyEvent> findByTestItemIdOrderByTriggeredAtDesc(@Param("testItemId") String testItemId);

    /**
     * 查询指定时间范围内的异常事件
     *
     * @param start 开始时间
     * @param end   结束时间
     * @return 异常事件列表
     */
    @Select("SELECT * FROM anomaly_event WHERE triggered_at BETWEEN #{start} AND #{end} ORDER BY triggered_at DESC")
    List<AnomalyEvent> findByTriggeredAtBetween(@Param("start") LocalDateTime start, @Param("end") LocalDateTime end);
}
