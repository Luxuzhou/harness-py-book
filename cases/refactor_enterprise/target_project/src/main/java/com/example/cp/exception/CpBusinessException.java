package com.example.cp.exception;

import lombok.Getter;

/**
 * 临床路径系统业务异常
 *
 * @author cp-team
 * @since 2024-01-10
 */
@Getter
public class CpBusinessException extends RuntimeException {

    private final String errorCode;
    private final String errorMessage;

    public CpBusinessException(CommonErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode.getCode();
        this.errorMessage = message;
    }

    public CpBusinessException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
        this.errorMessage = message;
    }

    public CpBusinessException(CommonErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode.getCode();
        this.errorMessage = errorCode.getMessage();
    }
}
