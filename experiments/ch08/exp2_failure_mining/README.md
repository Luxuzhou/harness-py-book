# Exp2: Failure Mining -> Rule Candidates

对应书稿 8.5：从失败到规则。

本实验从 `session.jsonl` 挖掘高频失败，按 `(tool, error_class)` 聚合，并生成可审计的候选变更。它同时兼容：

- 旧教学 schema：`role=tool/tool_name/error`
- 真实 runtime schema：`type=tool_call/tool/result_preview`

兼容逻辑位于 `experiments/ch08/feedback_loop.py`。

## 运行

```powershell
python -B experiments/ch08/exp2_failure_mining/run.py --no-synthesis --top 10
python -B experiments/ch08/exp2_failure_mining/run.py --sessions ".harness_sessions/*.jsonl" --no-synthesis
```

不带 `--sessions` 时使用 `sessions_sample/`。`--no-synthesis` 不调用 LLM，但仍会输出候选变更。

## 输出

- `results/failures_top.csv`：失败模式统计。
- `results/rule_candidates.json`：带 `target_layer`、`hypothesis`、`validation_plan`、`hard_gates` 的候选变更。
- `results/rules_candidate.md`：开启 LLM synthesis 时生成的人审报告。

## 工程要点

失败挖掘不是自动改 `CLAUDE.md`。它只生成候选变更；候选必须经过人工 review、离线 eval、red team gate、shadow/canary 后才允许进入生产规则。
