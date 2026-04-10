package com.example.sqc.model;

import com.mybatisflex.annotation.Column;
import com.mybatisflex.annotation.Id;
import com.mybatisflex.annotation.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 操作日志实体
 *
 * @author sqc-team
 * @since 2024-02-01
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Table("sqc_operation_log")
public class SqcOperationLog {

    @Id
    @Column("id")
    private String id;

    @Column("module")
    private String module;

    @Column("operation_type")
    private String operationType;

    @Column("operation_desc")
    private String operationDesc;

    @Column("target_type")
    private String targetType;

    @Column("target_id")
    private String targetId;

    @Column("request_method")
    private String requestMethod;

    @Column("request_url")
    private String requestUrl;

    @Column("request_params")
    private String requestParams;

    @Column("response_code")
    private String responseCode;

    @Column("response_message")
    private String responseMessage;

    @Column("operator")
    private String operator;

    @Column("operator_ip")
    private String operatorIp;

    @Column("operation_time")
    private LocalDateTime operationTime;

    @Column("elapsed_ms")
    private Long elapsedMs;

    @Column("lab_code")
    private String labCode;

    @Column("create_time")
    private LocalDateTime createTime;
}
