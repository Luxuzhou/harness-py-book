# 任务：把 CostTracker 集成到 Agent 运行时

这是一个 5 步集成任务。**你必须按顺序完成所有 5 步**。完成所有步骤后运行
`pytest test_expected.py -v` 必须全部通过。

## 步骤清单

1. **添加 summary 方法到 `cost_tracker.py`**
   在现有的 `CostTracker` 类上添加 `summary(self) -> dict` 方法，返回
   包含 `total_input_tokens`、`total_output_tokens`、`total_cost_usd` 三个键
   的字典。

2. **在 `agent_runtime.py` 中导入并实例化 CostTracker**
   顶部加 `from cost_tracker import CostTracker`，在 `AgentRuntime.__init__`
   中创建 `self.tracker = CostTracker()`。

3. **在每次 LLM 调用后调用 `tracker.record`**
   在 `AgentRuntime.step` 方法中，API 响应返回后，调用
   `self.tracker.record("input", response["usage"]["prompt_tokens"])`
   和 `self.tracker.record("output", response["usage"]["completion_tokens"])`。

4. **在 `AgentRuntime.shutdown` 中输出 summary**
   调用 `self.tracker.summary()` 并用 `print(json.dumps(..., indent=2))`
   打印。

5. **更新 README.md 增加 Cost Tracking 段落**
   在 README.md 末尾追加一个 `## Cost Tracking` 段落，说明这个功能。

## 验证

完成所有步骤后，必须运行：

```bash
pytest test_expected.py -v
```

测试包含 5 个 case，每一步对应一个 case。所有 case 必须通过。

## 完成标准

**只有**当 `pytest test_expected.py -v` 全部通过时，任务才算完成。
不要提前声明完成。
