# 实验任务：将CostTracker集成到Agent运行流程中

## 背景

`src/cost_tracker.py` 中有一个 `CostTracker` 类，但目前没有被任何模块引用。
现在需要将它集成到agent的运行流程中，实现按标签分类的token消耗跟踪。

## 需要完成的工作

### 1. 增强 cost_tracker.py

给 `CostTracker` 类新增一个 `summary()` 方法：
- 返回 `dict[str, int]`，key是标签名，value是该标签的总消耗
- 解析 events 列表中的 `"label:units"` 格式

### 2. 修改 agent_runtime.py

在 `LocalCodingAgent` 中集成 CostTracker：
- 在 `__init__` 或 `__post_init__` 中创建 `CostTracker` 实例
- 在 `_run_prompt` 方法的主循环中，每次模型调用后（约第574行附近 `total_usage = total_usage + turn.usage`），用 `tracker.record()` 记录 input_tokens 和 output_tokens
- 在 agent 运行结束时（`_run_prompt` 返回 `AgentRunResult` 前），将 tracker.summary() 的结果包含在输出中

### 3. 修改 openai_compat.py

在 `complete()` 和 `stream()` 方法返回的 `AssistantTurn` 中，确保 `usage` 字段包含模型名称信息，以便 agent_runtime 可以用模型名作为 CostTracker 的标签。

### 4. 编写测试

在 `tests/` 下新建测试文件，覆盖：
- CostTracker.summary() 方法
- agent_runtime 中 tracker 的集成逻辑（可以mock模型调用）

## 验证要求

完成所有修改后，必须执行以下验证：
1. 运行 `python -m pytest tests/test_cost_tracker.py -v` 确认原有测试全部通过
2. 运行你新写的测试文件，确认新测试全部通过
3. 如果任何测试失败，分析错误原因并修复，重新运行直到全部通过
4. 最后报告测试结果（通过数/总数）

## 约束

- 不要破坏现有的测试
- 不要修改 AgentRunResult 的签名（用现有字段传递信息）
- 代码风格与现有代码保持一致
- 修改的文件仅限：cost_tracker.py, agent_runtime.py, openai_compat.py, 以及新测试文件
