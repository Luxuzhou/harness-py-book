# Harness-py Book Project

## 项目概述
这是《驾驭AI》配套代码。当前任务是将CostTracker集成到Agent流程。

## 关键文件
- src/cost_tracker.py: CostTracker类，有record()方法但没有summary()
- harness_py/agent.py: 核心Agent循环

## 执行策略
1. 先规划再动手：列出所有需要修改的位置，确认后再编辑
2. 用grep定位，不要逐段read
3. 改完必须验证：运行 python -m pytest tests/ -v
4. 如果bash输出乱码，改用read_file直接检查代码

## Compact Instructions
压缩时保留：当前修改的文件列表、pytest结果、下一步计划
