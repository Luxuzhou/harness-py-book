package com.example.cp.exception;

/**
 * 预警规则已存在异常
 * <p>
 * 当尝试为已存在预警规则的诊疗项目创建新规则时抛出。
 * 对应 HTTP 409 Conflict 状态码。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
public class DuplicateRuleException extends RuntimeException {

    /** 诊疗项目ID */
    private final String testItemId;

    /**
     * 构造异常
     *
     * @param testItemId 已存在规则的诊疗项目ID
     */
    public DuplicateRuleException(String testItemId) {
        super("Rule already exists for test item: " + testItemId);
        this.testItemId = testItemId;
    }

    /**
     * 获取诊疗项目ID
     *
     * @return 诊疗项目ID
     */
    public String getTestItemId() {
        return testItemId;
    }
}
