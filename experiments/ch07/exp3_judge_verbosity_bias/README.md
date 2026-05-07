# exp3：Naive vs Best-Practice Judge 的 Verbosity Bias

对应书稿 **7.3 Generator-Evaluator 角色分离**。

## 研究问题

7.3 节核心断言："让 Agent 评判自己写的代码存在系统性偏差。Naive 实现的
Generator-Evaluator 模式不可靠，需要结构化的 Best-Practice judge 才能消除
verbosity / phrasing bias。"

> 同一份代码，仅替换 Agent 的自由文本回复，naive judge 的 verdict 是否
> 翻转？BP judge 在结构化输入下能否稳定按代码内容判断？

## 设计

### Fixtures（2 个）

| ID | 类型 | 设计意图 |
|---|---|---|
| `xm001` | 跨模块 regression | 修 `email_normalizer.py` 时必须验证 `dedup` 模块的 cross-module test |
| `dp001` | 弱测试 + spec 文件 | tests 只覆盖部分规则；完整规约在 `SPEC.md`；测试通过 ≠ 实现完成 |

### 9 个验证策略

| 策略 | Agent prompt | Judge |
|---|---|---|
| s1_baseline | 全量 pytest + 自评 | — |
| s2_test_selection | 只跑改动模块的测试 | — |
| s3_lint_first | py_compile → pytest | — |
| s4_independent_judge | 全量 pytest | naive judge（含 agent 自由文本） |
| s5_compressed_feedback | 全量 pytest，失败被 LLM 压缩到 ~150 字符 | — |
| s6_spec_aware | 强制读所有 .md 规约后再修 | — |
| s7_spec_aware_judge | s6 prompt + naive judge | naive judge |
| s8_bp_judge | 同 s4 prompt | best-practice judge（G-Eval 风格） |
| s9_spec_aware_bp_judge | 同 s6 prompt | best-practice judge |

### Naive judge vs Best-practice judge

| 维度 | naive (S4/S7) | best-practice (S8/S9) |
|---|---|---|
| Agent 自由文本作为输入 | 是 | 否 |
| 输出格式 | 自由文本 + 正则匹配 DONE | 强制 JSON schema |
| 评分粒度 | 单一综合 verdict | 每条规约独立 implemented_in_code |
| 采样 | 1 次 | 5 次多数投票 |
| Temperature | 0 | 0.3（让多采样有意义） |
| Verdict 推导 | LLM 自由给出 | 按"全规则 implemented + 测试通过 + 无作弊"硬规则推导 |

### 样本量

54 trials = 30（基线 5 策略 × 2 fixture × 3 seeds） + 12（s6/s7 factorial 补充）
+ 12（s8/s9 BP judge factorial 补充）。

## 结果

### Fixture xm001（跨模块 regression）

| 策略 | 通过率 | 平均 cost | judge 分布 |
|---|---|---|---|
| s1_baseline | 3/3 | $0.0062 | — |
| s2_test_selection | **0/3** | $0.0023 | — |
| s4_independent_judge | 3/3 | $0.0063 | DONE=1 NOT_DONE=2 |
| s7_spec_aware_judge | 3/3 | $0.0064 | DONE=1 NOT_DONE=2 |
| s8_bp_judge | 3/3 | $0.0059 | **DONE=3 NOT_DONE=0** |
| s9_spec_aware_bp_judge | 3/3 | $0.0054 | **DONE=3 NOT_DONE=0** |

观察：测试通过且代码正确的样本上，naive judge 仍有 67% 概率给 NOT_DONE；
BP judge 在同样样本上稳定 DONE。

### Fixture dp001（弱测试 + SPEC.md）

按 2x2 factorial（agent 是否被告知读 SPEC × judge 类型）排列：

| Cell | 策略 | 测试通过 | 实际代码 | judge verdict |
|---|---|---|---|---|
| A1 | s1_baseline (无 judge) | 3/3 | 不完整 | — |
| A3 | s6_spec_aware (无 judge) | 3/3 | **完整 4 类全实现** | — |
| A2 | s4 (naive judge) | 3/3 | 不完整 | DONE=0 NOT_DONE=3 |
| A4 | s7 (naive judge + spec) | 3/3 | **完整** | DONE=0 NOT_DONE=3 |
| A2\* | s8 (BP judge) | 3/3 | 不完整 | **DONE=0 NOT_DONE=3** |
| A4\* | s9 (BP judge + spec) | 3/3 | **完整** | **DONE=3 NOT_DONE=0** |

观察：naive judge 在不完整代码（A2）和完整代码（A4）上都 100% NOT_DONE → judge
输出与代码内容无关。BP judge 在 A2\*/A4\* 上分别给 100% NOT_DONE / 100% DONE
→ judge 输出与代码内容一致。

### Verbosity Bias 隔离实验

控制条件：固定 dp001/s7 seed=42 的完整代码，仅替换传入 judge 的 `agent_output`：

| Agent 最后回复 | naive judge verdict |
|---|---|
| "3 passed." | DONE |
| "3 passed, 0 failed，所有测试通过。" | NOT_DONE |
| "I implemented all 4 validation rules per SPEC.md..." | DONE |
| "修复完成。已按 SPEC.md 实现 4 类校验..." | DONE |

同代码下，verdict 仅因 agent_output 措辞改变。BP judge 在同矩阵上对完整代码
verdict=DONE 5/5，对不完整代码 verdict=NOT_DONE 5/5，与 agent_output 措辞无关。

## 结论

1. **Naive Generator-Evaluator 实现存在 verbosity / phrasing bias**：
   充分条件是 (a) judge prompt 包含 generator 的自由文本，(b) 输出走自由文本
   + 正则解析。引用对照：G-Eval (Liu et al., NeurIPS 2023) 已记录该 bias。

2. **Best-practice judge 可消除 verbosity bias**：去掉 agent_output、JSON
   结构化输出、每条规约独立打分、5 次采样多数投票、verdict 由硬规则推导。

3. **Spec-aware prompt 与 judge 选型相互独立**：可组合，可单独使用。

## 数据文件

| 文件 | trials | 说明 |
|---|---|---|
| `results/blindspot_30trials_final.jsonl` | 30 | 5 策略 × 2 fixture × 3 seeds 基线 |
| `results/factorial_12trials_final.jsonl` | 12 | naive judge 的 2x2 factorial 补充 |
| `results/bp_factorial_12trials_final.jsonl` | 12 | BP judge 的 2x2 factorial 补充 |

合计 54 trials。

## 复现命令

```bash
python experiments/ch07/exp3_judge_verbosity_bias/run.py \
    --tasks-set blindspot --strategy s8_bp_judge

python experiments/ch07/exp3_judge_verbosity_bias/run.py --fixture dp001
```
