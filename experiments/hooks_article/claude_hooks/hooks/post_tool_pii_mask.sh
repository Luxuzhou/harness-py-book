#!/bin/bash
# ============================================================
# PostToolUse Hook：PII 自动检测与警告
# ============================================================
# 对标 harness_py_pro 的 post_tool_hook 函数
# 对标《驾驭AI》第9章 §9.3.2 医疗PII脱敏
#
# 设计原则（来自《驾驭AI》第3章）：
#   post_tool 异常 → 放行（操作已执行，返回原始结果比报错更合理）
#
# Claude Code PostToolUse 实际传入的 JSON 结构：
#   .tool_name = "Read"
#   .tool_response.file.content = 文件内容
# ============================================================

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

# 只检查 Read 工具
if [ "$TOOL_NAME" != "Read" ]; then
    exit 0
fi

# 正确的字段路径：.tool_response.file.content
CONTENT=$(echo "$INPUT" | jq -r '.tool_response.file.content // empty')

if [ -z "$CONTENT" ]; then
    exit 0
fi

# 用 grep -E 检测身份证号（18位）
ID_CARD_COUNT=$(echo "$CONTENT" | grep -oE '[1-9][0-9]{5}(19|20)[0-9]{2}(0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])[0-9]{3}[0-9Xx]' | wc -l)

# 用 grep -E 检测手机号（11位）
PHONE_COUNT=$(echo "$CONTENT" | grep -oE '1[3-9][0-9]{9}' | wc -l)

if [ "$ID_CARD_COUNT" -gt 0 ] 2>/dev/null || [ "$PHONE_COUNT" -gt 0 ] 2>/dev/null; then
    echo "[PII Hook] 检测到 ${ID_CARD_COUNT} 个身份证号和 ${PHONE_COUNT} 个手机号。你在回复中必须脱敏：身份证号保留前6后4位，中间用*号替代；手机号保留前3后4位，中间用*号替代。绝对禁止原样输出任何身份证号或手机号。"
fi

exit 0
