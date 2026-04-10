package com.example.sqc.exception;

import lombok.Getter;

/**
 * 通用错误码
 *
 * @author sqc-team
 * @since 2024-01-10
 */
@Getter
public enum CommonErrorCode {

    // 通用错误
    SUCCESS("0", "操作成功"),
    SYSTEM_ERROR("SYS_001", "系统内部错误"),
    INVALID_PARAM("SYS_002", "参数校验失败"),
    UNAUTHORIZED("SYS_003", "未授权"),
    FORBIDDEN("SYS_004", "权限不足"),
    NOT_FOUND("SYS_005", "资源不存在"),
    TIMEOUT("SYS_006", "请求超时"),

    // 计划相关错误
    PLAN_NOT_FOUND("PLAN_001", "质控计划不存在"),
    DUPLICATE_PLAN("PLAN_002", "质控计划已存在"),
    PLAN_IN_USE("PLAN_003", "质控计划正在使用中"),
    PLAN_DISABLED("PLAN_004", "质控计划已禁用"),

    // 监控相关错误
    MONITOR_TASK_RUNNING("MON_001", "监控任务正在运行"),
    ALARM_NOT_FOUND("MON_002", "报警记录不存在"),

    // 数据相关错误
    DATA_NOT_FOUND("DATA_001", "检验数据不存在"),
    DATA_EXPORT_FAILED("DATA_002", "数据导出失败"),
    DATA_TOO_LARGE("DATA_003", "数据量过大"),

    // 队列相关错误
    QUEUE_SEND_FAILED("QUEUE_001", "消息发送失败"),
    QUEUE_CONSUME_FAILED("QUEUE_002", "消息消费失败");

    private final String code;
    private final String message;

    CommonErrorCode(String code, String message) {
        this.code = code;
        this.message = message;
    }
}
