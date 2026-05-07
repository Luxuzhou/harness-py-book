# exp4：LoopGuard 三层防御边际价值

对应书稿 **7.4 LoopGuard：检测死循环与恢复策略**（按 2026-04 调研后的修正版本）。

## 研究问题

7.4 节的传统叙事是"LoopGuard 把 69 次降到 3 次"。但 2026 年的现实更微妙：

- 现代模型（Claude 4.x、DeepSeek 2026-04+）在工具反馈错误时**有较强的自适应能力**
- LoopGuard 仍是 Claude Code、Cursor、LangChain 的内置组件，但已从"主角"降级为"兜底"
- DeerFlow #1261 (2026-03) 公开记录了 Claude Opus 4.6 在参数错配时仍 100+ 次重试

> 给定 3 类诱导 fixture，启用/不启用 LoopGuard 的最终任务成功率、轮数代价、
> 介入率、策略切换率分别是多少？LoopGuard 在 2026-04 DeepSeek 上的边际价值
> 是否如调研所言已经"边缘化"？

## 设计

### 四档防御对照（关键变量：模型自检 vs turn budget vs LoopGuard）

| 档 | turn budget | LoopGuard | reflection prompt | 含义 |
|---|---|---|---|---|
| **D0_naked** | 25 | NoOp | 无 | 最原始：仅靠 turn 上限兜底（业界最低保障的下限） |
| **D1_budget_only** | 15 | NoOp | 无 | 仅 turn budget = 15（业界事实标准） |
| **D2_with_guard** | 15 | 真启用 | 无 | 业界推荐的 LoopGuard 兜底（Claude Code、Cursor 都有） |
| **D3_full** | 15 | 真启用 | 在 prompt 里前置"重复失败时换工具" | 最完整版本（自检 + budget + guard） |

smoke 阶段先做 **D0 vs D2** 看核心边际价值。

### 三类诱导 fixture（按章节修正后的"三种循环模式"对应）

| Fixture | 诱导机制 | 对应 LoopGuard 检测 | 期望发现 |
|---|---|---|---|
| **F1_pytest_garble** | conftest 注入乱码字节到 stderr，模拟 7.4.2 章节的 DeepSeek 69 次乱码 | 检测 1（hash） | 现代模型不再被乱码困住 |
| **F2_edit_thrash** | 5 处相同 `status = "pending"`，edit_file 报 ambiguous | 检测 2（连续错误） | 自然 ambiguous 强模型能自己解决 |
| **F3_tool_unreliable** | pre_tool hook 让 edit_file 前 N 次返回固定错误（DeerFlow #1261 模式） | 检测 1（hash） | 工具不可靠时 Agent 多数能切换到 bash sed |
| **F4_locked_in** | hook 同时拦截 edit_file + bash 写文件命令，Agent 没替代工具 | 检测 1+2 | 极端约束下偶发真死循环 |

### 控制变量

- 模型：deepseek-chat，temperature=0
- planning_turns: 0
- 每 fixture × defense × 3 seeds（smoke）

### 关键指标

| 指标 | 含义 |
|---|---|
| `task_resolved` | 框架最终独立 pytest 是否通过 |
| `final_turns` / `cost_usd` | 总成本 |
| `intervention_count` | LoopGuard 触发次数 |
| `intervention_turn_first` | 首次介入轮数（0 = 未触发） |
| `edit_failures` | edit_file 调用中失败的次数 |
| `strategy_switched` | 介入后是否切换工具（介入前 3 轮 vs 介入后 3 轮的工具集差异） |

## Smoke 数据

### F1_pytest_garble（D0 vs D2，1 seed × 2 defense = 2 trials）

```
D0_naked       turns= 5  bash=2  edit=1  read=1  PASS
D2_with_guard  turns= 5  bash=2  edit=1  read=1  PASS  interv=0
```

**结论**：DeepSeek 没被 stderr 乱码困住——直接读 src + 一次 edit 修复。
章节修正：7.4.2 的"DeepSeek 69 次重试"故事在 2026-04 不可复现，但仍可作为
**轶事**保留来体现"早期模型的局限"。

### F2_edit_thrash（3 seeds × 2 defense = 6 trials）

```
D0_naked       avg_turns=5.3  avg_cost=$0.004  interv=0  switched=0/3  resolved=3/3
D2_with_guard  avg_turns=4.0  avg_cost=$0.003  interv=0  switched=0/3  resolved=3/3
```

**结论**：DeepSeek 看到 ambiguous error 后能自动扩展 old_string 加上下文 →
不触发 LoopGuard。**5 处相同字符串这种自然 ambiguity 不足以让现代模型跑飞**。

### F3_tool_unreliable（3 seeds × 2 defense = 6 trials，hook 拦截 edit_file 30 次）

```
D0_naked       avg_turns=9.0  edit=3(fail=3)  bash=2  resolved=3/3
D2_with_guard  avg_turns=9.0  edit=3(fail=3)  bash=2  interv=3  switched=3/3  resolved=3/3
```

**关键观察**：
- D0 和 D2 表现**几乎完全相同** → 现代 Agent 在 3 次相同失败后能自主切换工具
- D2 全部 3 trials LoopGuard 都在第 6 轮介入，且 `switched=3/3` → 介入信号是有效的
- **但介入是冗余的**——Agent 在收到提醒前就已经准备切换

D2 seed=42 完整轨迹（session log）：
```
read → glob → read → edit_file(FAIL) → edit_file(FAIL) → edit_file(FAIL)
   → [LOOP_GUARD] "edit_file 使用相同参数已调用 3 次，每次返回相同结果"
   → bash sed -i ...   ← 切换工具，任务完成
```
D0 seed=42 同样在 3 次 edit_file 失败后切到 bash sed。**LoopGuard 没起作用**。

### F4_locked_in（3 seeds × 2 defense = 6 trials，hook 同时拦截 edit_file + bash 写）

```
D0_naked       resolved=2/3  avg_turns=15.0  avg_cost=$0.011
              D0 seed=42: turns=25, edit=21(fail=21), task FAIL  ← 死循环！
              D0 seed=7,123: turns=10, 用 python -c 绕过 hook, PASS
D2_with_guard  resolved=3/3  avg_turns=10.0  avg_cost=$0.006
              全部 3 trials 用 python -c 绕过, 10 轮 PASS, interv=0
```

**关键发现**：在最严苛的 lock-in 约束下，**仍然只有 1/6 概率（D0 seed=42）**真正
陷入 21 次 edit_file 死循环。其他 5 trials Agent 用 `python -c "open().replace().write()"`
绕过了 hook 限制。

但 1/6 死循环发生时：
- turns: 25 vs 10 (**+150%**)
- cost: $0.022 vs $0.005 (**+340%**)

## 章节论点修正（按数据回填）

7.4 节的核心叙事建议改为：

1. **"LoopGuard 不是 2025 年描述的'核心组件'，是 2026 年的'低概率兜底'"**：
   F1/F2/F3 的 12 trials 中 LoopGuard 只在 F3 触发了 3 次（25%），且每次介入都是冗余的。

2. **"现代模型遇到工具失败时倾向于换工具而非反复重试"**：
   F3 的 D0 数据显示 Agent 在 3 次 edit_file 失败后自主切到 bash sed，**LoopGuard 无需介入**。

3. **"但'低概率'不是'零概率'，且尾部成本高"**：
   F4 的 D0 seed=42 trial 真陷入 21 次重试，cost 是其他 trials 的 4 倍。
   LoopGuard 的真实价值是**保护尾部分布**（与 Anthropic IterationBudget 思路一致）。

4. **"7.4.2 的 DeepSeek 69 次乱码故事"**：保留为历史 artifact，但不再当主案例。
   主案例换成 DeerFlow #1261（Claude Opus 4.6 在参数错配时 100+ 次重试）。

## 全量样本量

- smoke：3 fixtures × 2 defenses × 3 seeds = **15 trials**（已跑，约 ¥0.5）
- 全量：4 fixtures × 4 defenses × 5 seeds = **80 trials**（约 ¥3，30-40 分钟）
  - 4 fixtures = F1+F2+F3+F4
  - 4 defenses = D0+D1+D2+D3
  - 5 seeds 而不是 3：因为 F4 的 D0 跑飞是低概率事件，需要更多 seeds 才有统计意义

## 复现命令

```bash
# smoke（已跑过）
python run.py --fixture F4_locked_in --defenses D0_naked D2_with_guard --seeds 42 7 123

# 全量
python run.py --defenses D0_naked D1_budget_only D2_with_guard D3_full
```

## 限制

- 只测 DeepSeek 单模型——LoopGuard 在弱模型（如 7B 开源）上的价值未测
- F4 的 lock-in 是合成的，模拟"严格沙箱限制"而非自然死循环
- 介入提醒措辞固定为 LoopGuard 默认；不同措辞对 Agent 的影响未测
- 1/6 死循环概率的统计区间需要更大样本（建议 ≥ 30 seeds）才有显著性
- 若用 reasoning model（o1、Claude 4.6 extended thinking），介入率应进一步降低，
  跨模型对照实验留待后续
