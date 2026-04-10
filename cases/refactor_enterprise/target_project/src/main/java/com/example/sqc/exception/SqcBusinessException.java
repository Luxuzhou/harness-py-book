package com.example.sqc.exception;

import lombok.Getter;

/**
 * 质控系统业务异常
 *
 * @author sqc-team
 * @since 2024-01-10
 */
@Getter
public class SqcBusinessException extends RuntimeException {

    private final String errorCode;
    private final String errorMessage;

    public SqcBusinessException(CommonErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode.getCode();
        this.errorMessage = message;
    }

    public SqcBusinessException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
        this.errorMessage = message;
    }

    public SqcBusinessException(CommonErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode.getCode();
        this.errorMessage = errorCode.getMessage();
    }
}
