# Exp1: Cross-Layer Eval Framework

对应书稿 8.3：离线 Eval 基础设施。

本实验把 Ch4 的 capture-only 思路升级为通用 `Subject / Task / Runner`：

- `Subject`：被测对象，例如 tool description 或 system prompt。
- `Task`：Golden Set 的一条任务，包含期望工具调用和禁止信号。
- `Runner`：固定模型、seed、任务集，捕获 Agent 的工具调用序列并打分。

## 当前可测对象

- `tool_description`：复用 Ch4 的 V1/V2 工具描述。
- `system_prompt`：通过 `AgentConfig.role_prompt` 注入 V1/V2 提示词，不再依赖 monkey patch。

## 运行

```powershell
python -B experiments/ch08/exp1_eval_framework_extended/run.py --help
python -B experiments/ch08/exp1_eval_framework_extended/run.py --smoke --subject system_prompt
python -B experiments/ch08/exp1_eval_framework_extended/run.py --subject tool_description --version v2
```

`--smoke` 只跑少量任务和一个 seed；完整实验需要模型 API。

## 输出

- `results/raw_<subject>_<version>.jsonl`
- `results/summary_<subject>.json`

## 工程要点

这个实验验证的不是某个 prompt 一定更好，而是 eval 框架可以跨 Harness 层复用。真正的最佳实践是：被测对象通过正式配置面进入 engine，Runner、Golden Set、打分逻辑保持稳定。
