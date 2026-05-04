#!/bin/bash
# 调试脚本：把 PostToolUse 收到的完整 JSON 写入文件
INPUT=$(cat)
echo "$(date '+%H:%M:%S') =====" >> /tmp/hook_debug.log
echo "$INPUT" | jq '.' >> /tmp/hook_debug.log 2>&1 || echo "$INPUT" >> /tmp/hook_debug.log
echo "PostToolUse debug: logged to /tmp/hook_debug.log"
exit 0
