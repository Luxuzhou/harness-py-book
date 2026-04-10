package com.example.sqc.enums.plan;

import lombok.Getter;

/**
 * 质控算法枚举
 * <p>
 * 定义系统支持的所有质控算法类型。
 * </p>
 *
 * @author sqc-team
 * @since 2024-03-15
 */
@Getter
public enum AlgorithmEnum {

    WESTGARD("WESTGARD", "Westgard多规则", "经典Westgard多规则质控方法，支持1-3s/2-2s/R-4s/4-1s/10x等规则"),
    MOVING_AVERAGE("MOVING_AVG", "移动均值法", "基于患者数据的移动均值质控方法"),
    CUSUM("CUSUM", "累积和法", "累积和控制图方法，适用于系统偏移检测"),
    EWMA("EWMA", "指数加权移动平均", "指数加权移动平均控制图，对小偏移敏感"),
    GRUBBS("GRUBBS", "Grubbs异常值检验", "Grubbs检验法用于离群值检测"),
    LEVEY_JENNINGS("LJ", "Levey-Jennings图", "经典Levey-Jennings质控图"),
    SIX_SIGMA("SIX_SIGMA", "六西格玛", "基于六西格玛方法学的质控评估");

    private final String code;
    private final String name;
    private final String description;

    AlgorithmEnum(String code, String name, String description) {
        this.code = code;
        this.name = name;
        this.description = description;
    }

    public static AlgorithmEnum fromCode(String code) {
        if (code == null) return null;
        for (AlgorithmEnum e : values()) {
            if (e.getCode().equals(code)) {
                return e;
            }
        }
        return null;
    }
}
