# Ch8 实验索引

对应书稿第 8 章《反馈调节：让 Harness 自我演化》。

本章是全书的 controller 章。前 7 章构造 Harness 的 plant：约束、工具、上下文、记忆、验证、编排。第 8 章验证 controller：Observe -> Diagnose -> Candidate -> Gate -> Shadow/Canary -> Promote/Rollback -> Update Golden Set。

## 当前实验

| 编号 | 目录 | 对应章节 | 状态 | 能验证什么 |
| --- | --- | --- | --- | --- |
| kernel | `../check_ch08_kernel.py` | 全章工程闭环 | 可直接跑，无 LLM | 验证真实 session schema、失败挖掘、候选规则、发布门禁、prompt 注入、rollback manifest |
| exp1 | `exp1_eval_framework_extended/` | 8.3 离线 Eval 基础设施 | 可运行，需要 API | 通用 Subject / Task / Runner；system prompt subject 通过 `AgentConfig.role_prompt` 注入，不依赖 monkey patch |
| exp2 | `exp2_failure_mining/` | 8.5 从失败到规则 | 可直接跑，无 LLM 时用 `--no-synthesis` | 同时消费旧样例日志和真实 `.harness_sessions/*.jsonl`，输出失败统计和 `rule_candidates.json` |
| exp3 | `exp3_redteam_goldenset/` | 8.7 Red Team Golden Set | 可运行，需要 API | baseline vs defense 的攻击成功率/拦截率；prompt 版本通过正式配置面注入 |
| exp4 | `exp4_pareto/` | 8.6 Shadow + 8.8 Pareto 前沿 | 部分需 API | Pareto: 多配置 Accuracy × Cost 对比与前沿识别；Shadow: offline/live 双模式会话差异比较 |

## 最小本地验证

```powershell
python -B experiments/check_ch08_kernel.py
python -B examples/ch08_feedback.py
python -B experiments/ch08/exp2_failure_mining/run.py --no-synthesis --top 10
python -B experiments/ch08/exp4_pareto/shadow_demo.py
```

这些命令不调用 LLM，用来验证第 8 章工程闭环本身是否稳定。需要模型 API 的实验再运行：

```powershell
python -B experiments/ch08/exp1_eval_framework_extended/run.py --smoke --subject system_prompt
python -B experiments/ch08/exp3_redteam_goldenset/run.py --smoke --version all
```

## 工程口径

- 失败挖掘统一走 `feedback_loop.py`，避免 example、exp2、后续生产分析各维护一套分类规则。
- `SessionWriter.write_tool_call()` 同时写出当前 schema 和兼容字段：`type/tool/result_preview` 与 `role/tool_name/error`。
- `RuleCandidate` 不是自动合入生产规则，而是携带来源、目标层、假设、验证计划和硬门禁的候选变更。
- Prompt A/B 通过 `AgentConfig.role_prompt` 注入，Red Team 防御段通过 `AgentConfig.system_prompt_append` 注入；二者都走 engine 的正式配置面。
- 安全回归是硬门禁；Accuracy x Cost 的 Pareto 只用于通过安全门后的候选排序。
