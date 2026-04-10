package com.example.sqc.mapper.ck;

import com.example.sqc.model.ck.BiInspectResult;
import com.mybatisflex.core.BaseMapper;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * ClickHouse检验结果Mapper
 * <p>
 * 连接ClickHouse数据源，查询检验结果宽表数据。
 * 注意：此Mapper使用独立的ClickHouse数据源，不参与MySQL事务。
 * </p>
 *
 * @author sqc-team
 * @since 2024-01-10
 */
@Mapper
public interface BiInspectResultMapper extends BaseMapper<BiInspectResult> {

    /**
     * 按条件查询检验结果（坏味道：SQL字符串拼接，且条件较复杂）
     */
    @Select("<script>" +
            "SELECT * FROM bi_inspect_result " +
            "WHERE lab_code = #{labCode} " +
            "AND instrument_code = #{instrumentCode} " +
            "AND item_code = #{itemCode} " +
            "<if test='controlLotNo != null and controlLotNo != \"\"'>" +
            "AND control_lot_no = #{controlLotNo} " +
            "</if>" +
            "AND inspect_time BETWEEN #{startTime} AND #{endTime} " +
            "AND is_deleted = 0 " +
            "ORDER BY inspect_time ASC " +
            "LIMIT 50000" +
            "</script>")
    List<BiInspectResult> queryByCondition(
            @Param("labCode") String labCode,
            @Param("instrumentCode") String instrumentCode,
            @Param("itemCode") String itemCode,
            @Param("controlLotNo") String controlLotNo,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    /**
     * 查询质控样本数据
     */
    @Select("SELECT * FROM bi_inspect_result " +
            "WHERE lab_code = #{labCode} " +
            "AND instrument_code = #{instrumentCode} " +
            "AND item_code = #{itemCode} " +
            "AND is_qc_data = 1 " +
            "AND control_level = #{controlLevel} " +
            "AND inspect_time BETWEEN #{startTime} AND #{endTime} " +
            "AND is_deleted = 0 " +
            "ORDER BY inspect_time ASC")
    List<BiInspectResult> queryQcSamples(
            @Param("labCode") String labCode,
            @Param("instrumentCode") String instrumentCode,
            @Param("itemCode") String itemCode,
            @Param("controlLevel") Integer controlLevel,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    /**
     * 按日期统计检验量
     */
    @Select("SELECT toDate(inspect_time) as inspect_date, COUNT(*) as cnt " +
            "FROM bi_inspect_result " +
            "WHERE lab_code = #{labCode} " +
            "AND inspect_time BETWEEN #{startTime} AND #{endTime} " +
            "AND is_deleted = 0 " +
            "GROUP BY inspect_date " +
            "ORDER BY inspect_date ASC")
    List<java.util.Map<String, Object>> countByDate(
            @Param("labCode") String labCode,
            @Param("startTime") LocalDateTime startTime,
            @Param("endTime") LocalDateTime endTime);

    /**
     * 查询仪器列表（去重）
     */
    @Select("SELECT DISTINCT instrument_code, instrument_name " +
            "FROM bi_inspect_result " +
            "WHERE lab_code = #{labCode} " +
            "AND is_deleted = 0 " +
            "ORDER BY instrument_code")
    List<java.util.Map<String, Object>> findDistinctInstruments(@Param("labCode") String labCode);
}
