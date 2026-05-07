# 实验五：三步唤醒对恢复后质量的影响

对应书稿 **6.5.3 恢复后的状态确认三步流程**。

## 研究问题

> 会话中断并恢复后，让 Agent 先执行"pwd / git log / 读 TASK.md"三步唤醒，
> 是否显著降低恢复后前 5 轮内出现的"错误目录 / 过时文件假设 / 重复执行
> 已完成步骤"这三类低级错误的发生率？

章节当前的论断（第 932-935 行）：**唤醒后的 Agent 能更快回到可工作状态。
对长任务来说，恢复后的前几轮往往决定了任务是重新进入正轨，还是继续跑偏。**
本实验给这一断言量化指标。

## 外部对标

- Anthropic *Effective Harnesses*（2025-11）：提出三步唤醒最佳实践，无量化
  数据。
- Claude Code `--resume` 文档：说明 file_history_replay 和 compaction_replay
  消息的作用。

本实验是三步唤醒效果的首次独立量化测量。

## 实验设定

**任务**：一个 10 步代码重构任务（参见 `fixtures/task_description.md`）。
每一步都要修改文件并跑 pytest。

**中断策略**：让 Agent 跑到第 5 步完成后，通过 `SIGINT` 或超时中断，
生成 session jsonl 文件。

**恢复策略**（自变量）：
- `plain_prompt`: "请继续之前未完成的工作。"
- `three_step_wakeup`: """
    在继续任务前，先完成状态确认：
    1. 运行 `pwd` 输出当前工作目录
    2. 运行 `git log --oneline -10` 查看最近变更
    3. 读取 TASK.md 获取任务进度
    然后根据 TASK.md 的进度继续执行剩余步骤。"""

**因变量**：
- `wrong_dir_errors`: 前 5 轮内引用错误路径的次数（如试图读不存在的文件）
- `stale_assumptions`: 前 5 轮内假设某文件内容还是旧版本（实际已被修改）的次数
- `repeated_steps`: 前 5 轮内重复执行第 1-5 步（已完成）的次数
- `time_to_first_productive_turn`: 恢复后第一次"正确推进到新步骤"的轮数
- `final_pytest_pass`: 任务最终是否全部通过 pytest（5-10 步的通过数）

**控制变量**：
- 模型：`deepseek-chat`
- 中断点固定在第 5 步完成后
- 任务描述完全相同
- CLAUDE.md 内容相同（含标准项目约定，不含 Compact Instructions）
- preserve_messages=4, threshold=0.80

**样本量**：
- `--smoke`：每组 2 次，共 4 次
- 全量：每组 8 次，共 16 次

## 成本估算

- 单次 10 步任务约 40K 输入 + 8K 输出 token ≈ $0.02
- 每次 trial 跑两次（中断 + 恢复），约 $0.04
- 全量 ≈ $0.6

## 实际产出

- `results/raw.jsonl`：每次 trial 的完整记录（16 行，2 variants × 8 seeds）
- 当前仓库只保留 `raw.jsonl` 落盘，未生成 `summary.csv` 和 PNG 图

## 复现命令

```bash
python experiments/ch06/exp5_resume_awakening/run.py --smoke
python experiments/ch06/exp5_resume_awakening/run.py
```

## 实测结果（2026-04，DeepSeek-V3，8 seeds × 2 variants = 16 trials）

| 指标 | plain | three_step |
|------|-------|-----------|
| first_productive_turn 均值 | 1.88 | 4.00 |
| final_completed_steps 均值 | 4.50 | 3.38 |
| wrong_dir_errors 均值 | 0.00 | 0.00 |

关键结论（已回填书稿 6.5.3 节）：

- **三步唤醒不是加速器，而是减振器**。plain 首次推进更快（均值 1.88 轮），但方差大（8 次里有 -1、1、2、5 等不同值）；three_step 每次都固定 4 轮（3 轮状态确认 + 1 轮真正推进），方差 ≈ 0。
- **适用场景**：跨进程、跨时间、多 Agent 交接等环境不确定场景，用 3 轮固定开销换取恢复过程的确定性，而非在同一进程内同一任务内"加速恢复"。
- **wrong_dir_errors** 在两组都是 0：本实验任务规模（10 步）不足以暴露"错走路径"的失败模式；更长任务可能放大。

## 限制

- 判定"错误目录"、"过时假设"需要解析 session 轨迹的启发式规则，存在误判。
- TASK.md 文件需要 Agent 在工作过程中自行维护。如果 Agent 未按 prompt 指令
  维护，第三步唤醒会降级为"读一个空文件"。这是已知的测量偏差。
- 10 步任务规模有限。更长的任务（50+ 步）可能放大或缩小这个效应。
