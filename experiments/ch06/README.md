# Ch6 实验索引

对应书稿《第6章 记忆管理与上下文压缩》。本章的核心论点需要本书实验支撑，
外部文献（Anthropic、Hermes、DeerFlow、DeepAgents）只作为参照基线。

## 实验总览

| 实验 | 对应章节 | 外部对标 | 是否需要 LLM API |
|---|---|---|---|
| `exp1_snr_decay/` | 6.1.1 信噪比塌陷 | Anthropic "Context Rot" | 是（可禁用 judge 做纯结构测量） |
| `exp2_compression_triggers/` | 6.2 四级压缩 / 6.3 预算 | Hermes 迭代摘要 | 是 |
| `exp3_compact_instructions/` | 6.6.3 任务目标保持 | 无直接对标 | 是 |
| `exp4_dream_consolidation/` | 6.4.3 Dream 整理 | Claude Code Dream | 否（规则式，可选 LLM 语义合并） |
| `exp5_resume_awakening/` | 6.5.3 三步唤醒 | Anthropic 最佳实践 | 是 |

## 实验设计原则

本章所有实验遵循下列约束，对齐经典技术书（Deep Learning、DDIA、CS:APP）的实证章节写法：

1. **明确的研究问题**。每个实验在 `README.md` 顶部用一句话陈述要回答的问题。
2. **受控变量**。自变量单一（偶尔双因子），其余固定。每个实验注明固定了什么。
3. **可复现性**。每个实验支持 `--smoke`（最小规模，几美元成本）和全量两档。
   `--smoke` 下的种子/样本固定，任何读者跑出来应和作者数据趋势一致。
4. **多次采样**。全量模式每个配置至少跑 3 个随机种子，产出均值加标准差。
5. **独立验证**。不依赖 Agent 自报的"完成了"。pytest、LLM-as-judge、规则检查等
   外部度量才算数据。
6. **对照现有文献**。每个实验的 Discussion 段必须说明结果和哪条外部断言一致或相左。

## 复现路径

推荐按下列四步执行。exp4 不需 API，可立即跑通验证环境。

```bash
cd harness-py-book

# 0. 设置环境（API key）
cp .env.example .env  # 填入 HARNESS_API_KEY

# 1. 立即可跑（无需 API，约 5 秒完成，可直接回填 6.4.3 节）
python experiments/ch06/exp4_dream_consolidation/generate_fixtures.py
python experiments/ch06/exp4_dream_consolidation/run.py

# 2. 冒烟验证其他 4 个（总成本约 $2，约 30 分钟）
python experiments/ch06/exp1_snr_decay/generate_fixtures.py   # 首次需要
python experiments/ch06/exp1_snr_decay/run.py --smoke
python experiments/ch06/exp2_compression_triggers/run.py --smoke
python experiments/ch06/exp3_compact_instructions/run.py --smoke
python experiments/ch06/exp5_resume_awakening/run.py --smoke

# 3. 全量（总成本估算约 $6-8，约 4 小时）
#    单项估算：exp1 ~$3，exp2 ~$2.5，exp3 ~$0.2，exp5 ~$0.6
for exp in exp1_snr_decay exp2_compression_triggers \
           exp3_compact_instructions exp5_resume_awakening; do
  python experiments/ch06/$exp/run.py
done

# 4. 重绘图表（不重跑实验）
python experiments/ch06/exp1_snr_decay/plot.py
python experiments/ch06/exp2_compression_triggers/plot.py
```

说明：
- exp1 和 exp4 首次运行需要先跑 `generate_fixtures.py` 生成夹具。夹具是
  Python / Markdown 文件，被版本控制，生成一次即可。
- exp3 和 exp5 的夹具全部检入在 `fixtures/` 目录，无需生成。
- 冒烟验证只跑最小规模（2 seeds × 最少配置），用于在跑全量前确认环境和
  代码无 bug。如果冒烟已经暴露问题，先修再跑全量。

## 产出约定

每个实验目录下：

```
expN_<name>/
├── README.md           设计文档 + 研究问题 + 复现命令 + 讨论框架
├── run.py              主入口，支持 --smoke
├── plot.py             图表生成（独立入口，可加载已有结果）
├── fixtures/           实验夹具（被版本控制）
└── results/            原始数据输出（加入 .gitignore）
    ├── raw.jsonl       每次运行的原始记录
    ├── summary.csv     聚合后的指标表
    └── figures/        PNG 图表
```

章节正文引用 `experiments/ch06/expN_<name>/` 时，必须引用到具体文件或函数，
禁止只引用目录名。

## 状态追踪

- [x] **exp1_snr_decay** — 已跑，数据已回填书稿 6.1.1 节
- [x] **exp2_compression_triggers** — 已跑（3 preserve × 3 threshold × 2 seeds = 18 trials），数据已回填 6.2/6.3
- [x] **exp3_compact_instructions** — 已跑（three variants × 10 seeds = 30 trials；without / with / with_structured），数据已回填 6.6.3
- [x] **exp4_dream_consolidation** — 已端到端跑通：10 文件，总行数 344→290（降 **15.7%**），逐文件平均缩减率 **5.84%**（最高 19.8%），4 处去重，13 处相对日期转绝对日期；Dream 实现保护 YAML front matter，`---` 不会被去重误删
- [x] **exp5_resume_awakening** — 已跑（plain vs three_step × 8 seeds = 16 trials）。**关键结论：three_step 不是加速器，而是减振器**——平均首次推进更慢（three_step 4.00 轮 vs plain 1.88 轮），完成步骤更少（3.38 vs 4.50），但方差显著下降（plain first-productive 标准差大，three_step 每次都稳定 4 轮）；适合跨进程、跨时间、多 Agent 交接等环境不确定场景

实验数据已全部回填正文。如需重跑：

1. 跑 `--smoke` 验证脚本无 bug
2. 跑全量，产出 `results/raw.jsonl` 和 `results/summary.csv`
3. 在章节对应小节重新核对数字与图表
