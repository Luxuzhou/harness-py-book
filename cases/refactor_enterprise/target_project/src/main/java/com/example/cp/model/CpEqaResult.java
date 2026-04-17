package com.example.cp.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 室间质评结果实体
 *
 * @author cp-team
 * @since 2024-02-20
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("cp_eqa_result")
public class CpEqaResult {

    @Id
    @Column("id")
    private String id;

    @Column("program_code")
    private String programCode;

    @Column("program_name")
    private String programName;

    @Column("eqa_year")
    private String eqaYear;

    @Column("eqa_batch")
    private String eqaBatch;

    @Column("lab_code")
    private String labCode;

    @Column("instrument_code")
    private String instrumentCode;

    @Column("item_code")
    private String itemCode;

    @Column("item_name")
    private String itemName;

    @Column("reported_value")
    private BigDecimal reportedValue;

    @Column("target_value")
    private BigDecimal targetValue;

    @Column("peer_mean")
    private BigDecimal peerMean;

    @Column("peer_sd")
    private BigDecimal peerSd;

    @Column("z_score")
    private BigDecimal zScore;

    @Column("result_grade")
    private String resultGrade;

    @Column("evaluation_status")
    private Integer evaluationStatus;

    @Column("create_time")
    private LocalDateTime createTime;

    @Column("update_time")
    private LocalDateTime updateTime;

    @Column("is_deleted")
    private Integer isDeleted;
}
