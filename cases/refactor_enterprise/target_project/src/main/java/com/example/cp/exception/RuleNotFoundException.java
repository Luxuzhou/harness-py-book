package com.example.cp.exception;

/**
 * 预警规则不存在异常
 * <p>
 * 当查询不存在的预警规则时抛出。
 * 对应 HTTP 404 Not Found 状态码。
 * </p>
 *
 * @author cp-team
 * @since 2024-03-20
 */
public class RuleNotFoundException extends RuntimeException {

    /** 诊疗项目ID */
    private final String testItemId;

    /**
     * 构造异常
     *
     * @param testItemId 不存在的诊疗项目ID
     */
    public RuleNotFoundException(String testItemId) {
        super("Rule not found for test item: " + testItemId);
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
