# Ch7 exp1：闭环验证策略对照实验

## 数据文件

| 文件 | trials | 说明 |
|---|---|---|
| `blindspot_30trials_final.jsonl` | 30 | 基线 5 策略 × 2 fixture × 3 seeds |
| `factorial_12trials_final.jsonl` | 12 | naive judge 的 2x2 factorial 补充（S6/S7） |
| `bp_factorial_12trials_final.jsonl` | 12 | best-practice judge 的 factorial 补充（S8/S9） |
| `raw.jsonl` | 变动 | 最近一次 run 的原始输出，会被覆盖 |
| `_archive/` | — | 历史无关数据 |

合并 trials = 54。

## Fixture 与策略

### Fixtures（2 个）

| ID | 类型 | 设计意图 |
|---|---|---|
| `xm001` | 跨模块 regression | 修 `email_normalizer.py` 的同时必须验证 `dedup` 模块的 cross-module test |
| `dp001` | 弱测试 + spec 文件 | tests 只覆盖部分规则；完整规约在 `SPEC.md`；测试通过 ≠ 实现完成 |

### 策略（9 个）

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

### Naive judge vs best-practice judge

| 维度 | naive (S4/S7) | best-practice (S8/S9) |
|---|---|---|
| Agent 自由文本作为输入 | 是 | 否 |
| 输出格式 | 自由文本 + 正则匹配 DONE | 强制 JSON schema |
| 评分粒度 | 单一综合 verdict | 每条规约独立 implemented_in_code |
| 采样 | 1 次 | 5 次多数投票 |
| Temperature | 0 | 0.3（让多采样有意义） |
| Verdict 推导 | LLM 自由给出 | 按"全规则 implemented + 测试通过 + 无作弊"硬规则推导 |

## 结果

### Fixture xm001（跨模块 regression）

| 策略 | 通过率 | 平均 cost | 平均 turns | judge 分布 |
|---|---|---|---|---|
| s1_baseline | 3/3 | $0.0062 | 8.00 | — |
| s2_test_selection | **0/3** | $0.0023 | 4.00 | — |
| s3_lint_first | 1/3 | $0.0042 | 6.00 | — |
| s5_compressed_feedback | 2/3 | $0.0056 | 8.00 | — |
| s4_independent_judge | 3/3 | $0.0063 | 8.00 | DONE=1 NOT_DONE=2 |
| s7_spec_aware_judge | 3/3 | $0.0064 | 6.67 | DONE=1 NOT_DONE=2 |
| s8_bp_judge | 3/3 | $0.0059 | 7.67 | **DONE=3 NOT_DONE=0** |
| s9_spec_aware_bp_judge | 3/3 | $0.0054 | 5.67 | **DONE=3 NOT_DONE=0** |

观察：
- s2 跨模块测试不跑 → 通过率 0；其余 4 档闭环策略 ≥ 2/3。s2 vs s1 cost 比 = 0.37×。
- s4/s7（naive judge）verdict 分布 (1,2)：在测试通过且代码正确的样本上，naive judge 仍有 67% 概率给 NOT_DONE。
- s8/s9（BP judge）verdict 分布 (3,0)：在同样样本上稳定 DONE，无过度严格倾向。

### Fixture dp001（弱测试 + SPEC.md）

dp001 上 5 档基础策略均能让测试通过（测试只覆盖 username/email），差异化在"实际实现是否完整"和"judge verdict"两个维度。

按 2x2 factorial（agent 是否被告知读 SPEC × judge 类型）排列：

| Cell | 策略 | 测试通过 | 实际代码 | judge verdict |
|---|---|---|---|---|
| A1 | s1_baseline (无 judge) | 3/3 | 不完整（仅 username/email） | — |
| A3 | s6_spec_aware (无 judge) | 3/3 | **完整 4 类全实现** | — |
| A2 | s4 (naive judge) | 3/3 | 不完整 | DONE=0 NOT_DONE=3 |
| A4 | s7 (naive judge + spec) | 3/3 | **完整** | DONE=0 NOT_DONE=3 |
| A2\* | s8 (BP judge) | 3/3 | 不完整 | **DONE=0 NOT_DONE=3** |
| A4\* | s9 (BP judge + spec) | 3/3 | **完整** | **DONE=3 NOT_DONE=0** |

观察：
- A1 vs A3：仅向 agent 说"读 SPEC.md" → 实现从不完整变完整，cost +60%（$0.0046 → $0.0074）。
- A2 vs A4：naive judge 在不完整代码（A2）和完整代码（A4）上都 100% NOT_DONE → judge 输出与代码内容无关。
- A2\* vs A4\*：BP judge 在不完整代码上 100% NOT_DONE，在完整代码上 100% DONE → judge 输出与代码内容一致。

### Naive judge 偏见隔离实验

控制条件：固定 dp001/s7 seed=42 的完整代码，仅替换传入 judge 的 `agent_output` 字段。

| Agent 最后回复 | naive judge verdict |
|---|---|
| "3 passed." | DONE |
| "3 passed, 0 failed，所有测试通过。" | NOT_DONE |
| "I implemented all 4 validation rules per SPEC.md..." | DONE |
| "修复完成。已按 SPEC.md 实现 4 类校验..." | DONE |

同代码下，verdict 仅因 agent_output 措辞改变，差异为 1 hit。判定该差异由 verbosity / phrasing 引起。

对照：BP judge 在同样矩阵上对完整代码 verdict=DONE 5/5，对不完整代码 verdict=NOT_DONE 5/5，与 agent_output 措辞无关（详见 chapter 文稿）。

## 推论

1. **测试选择策略与 cross-module regression 不兼容**：xm001 上 s2 通过率 = 0，其余闭环策略 ≥ 67%。前提：fixture 含跨模块依赖且依赖文件不在 agent 的"改动模块"集合内。

2. **Naive Generator-Evaluator 实现存在 verbosity / phrasing bias**：
   - 充分条件：(a) judge prompt 包含 generator 的自由文本，(b) 输出走自由文本 + 正则解析。
   - 表现：同代码下 verdict 取决于 generator 回复措辞而非代码内容。
   - 引用对照：G-Eval (Liu et al., NeurIPS 2023) 等已记录 LLM-as-judge 的 verbosity bias。

3. **Best-practice judge 设计可消除 verbosity bias**：
   - 实现：去掉 agent_output、JSON 结构化输出、每条规约独立打分、5 次采样多数投票、verdict 由硬规则推导而非 LLM 自由给出。
   - 验证：dp001 A4\* (DONE=3/3 on 完整代码) vs A4 (NOT_DONE=3/3 on 同代码) → bias 消失。
   - 验证：xm001 s8/s9 (DONE=3/3 on 通过测试代码) vs s4/s7 (DONE=1/3 on 同样本) → 无 false-NOT_DONE 倾向。

4. **Spec-aware prompt 与 judge 选型相互独立**：
   - 不读 spec + BP judge（A2\*）能识别不完整实现，无需依赖 agent 主动读 spec。
   - 读 spec + BP judge（A4\*）能识别完整实现，无 false NOT_DONE。
   - 二者可组合也可单独使用。

## 复现命令

```bash
# 基线 30 trials
python experiments/ch07/exp3_judge_verbosity_bias/run.py --tasks-set blindspot

# Naive judge factorial 补充
python experiments/ch07/exp3_judge_verbosity_bias/run.py --tasks-set blindspot --strategy s6_spec_aware
python experiments/ch07/exp3_judge_verbosity_bias/run.py --tasks-set blindspot --strategy s7_spec_aware_judge

# BP judge factorial 补充
python experiments/ch07/exp3_judge_verbosity_bias/run.py --tasks-set blindspot --strategy s8_bp_judge
python experiments/ch07/exp3_judge_verbosity_bias/run.py --tasks-set blindspot --strategy s9_spec_aware_bp_judge
```

## 已下架的论点

| 论点 | 证伪依据 |
|---|---|
| "S5 压缩反馈丢信息" | lt001 fixture 失败：agent 直接读 cases.py 绕过压缩，5 档全 3/3 通过 |
| "S3 lint-first 显著降本" | 实测仅多 1 次 py_compile 调用，对 cost 无显著影响 |
| "Naive GE 模式能识别不完整实现" | A4 反例：完整代码也被 100% 判 NOT_DONE，verdict 由 agent 措辞决定 |
| "GE 模式有结构性脆弱性"（早期主张） | A4\* 证伪：BP judge 在 A2\*/A4\* 上分别正确给 NOT_DONE/DONE，pattern 本身可用，naive 实现脆弱而已 |
