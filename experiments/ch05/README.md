# Ch5 实验索引

第5章"上下文工程与 Prompt Cache"的全部实证代码。三个实验对应章节里的三条
外部断言，在 DeepSeek + harness-py 上做一手验证。

## 实验清单

| 目录 | 对应章节 | 要验证的断言 | 状态 |
|------|----------|--------------|------|
| `exp1_agents_md_length/` | 5.1.3 | 过度详细的 AGENTS.md 反而增加成本（ETH, arXiv:2602.11988） | **已跑**（3 任务 × 4 档 × 5 seeds = 60 次），数据已回填 |
| `exp2_cache_stability/` | 5.4.3 / 5.5.2 / 5.5.4 | 前缀稳定性决定 Cache 命中率，经验值"85%+"可量化 | **已跑**（5 配置 × 30 轮 = 150 次），数据已回填 |
| `exp3_prohibition_wording/` | 5.1.2 | 禁令措辞 vs 正向指导的遵从率差异 | **已跑**（5 对 × 2 措辞 × 10 次 = 100 次），结论：禁令不是普遍更强，取决于推荐方案易用性；AGENTS.md 高风险规则应写成"禁令 + 替代路径"双段式 |

## 执行路径

### 前置条件

```bash
# 1. 根目录下的 .env 必须配置 DeepSeek API key
# 其中至少包含：
#   OPENAI_API_KEY=sk-...
#   OPENAI_BASE_URL=https://api.deepseek.com/v1
#   OPENAI_MODEL=deepseek-chat

# 2. 确认 Python 依赖
cd D:/Working_Tools/Projects/harness-py-book
pip install -e . 2>/dev/null || pip install -r requirements.txt
```

### 冒烟测试（建议先跑一遍确认环境，共约5分钟）

```bash
cd D:/Working_Tools/Projects/harness-py-book

# 实验一 smoke（1任务×1档×1种子=1次）
python experiments/ch05/exp1_agents_md_length/run.py --smoke

# 实验二 smoke（2配置×3轮=6次）
python experiments/ch05/exp2_cache_stability/run.py --smoke

# 实验三 smoke（2对×2措辞×2次=8次，Windows需 PYTHONIOENCODING=utf-8）
$env:PYTHONIOENCODING="utf-8"; python experiments/ch05/exp3_prohibition_wording/run.py --smoke
```

### 全量运行（按顺序）

```bash
cd D:/Working_Tools/Projects/harness-py-book

# 实验一：AGENTS.md 长度效应（约 90 分钟，约 $1.5）
# 3 任务 × 4 档 × 5 种子 = 60 次
python experiments/ch05/exp1_agents_md_length/run.py

# 实验二：Cache 前缀稳定性（约 25 分钟，约 $0.2）
# 5 配置 × 30 轮 = 150 次
python experiments/ch05/exp2_cache_stability/run.py

# 实验三：禁令措辞遵从率（约 15 分钟，约 $0.1）
# 5 对 × 2 措辞 × 10 次 = 100 次
PYTHONIOENCODING=utf-8 python experiments/ch05/exp3_prohibition_wording/run.py
```

**总计**：约 130 分钟 / 约 $2。三个实验**不可并行跑**（避免 DeepSeek API
限流和 Cache 命中率互相干扰）。

### 参数化运行

每个实验都支持细粒度控制，详见该目录下的 `README.md`。常用模式：

```bash
# 只跑单任务单档位（调试用）
python experiments/ch05/exp1_agents_md_length/run.py --task cost_tracker_bug --variant L2 --seeds 1

# 只跑特定配置（对比不完整数据集）
python experiments/ch05/exp2_cache_stability/run.py --configs A,B,C --rounds 15

# 只跑单对规则
python experiments/ch05/exp3_prohibition_wording/run.py --pairs eval_usage --n 5
```

## 数据产出与章节映射

| 实验数据 | 写入章节位置 | 替换/新增 |
|---------|------------|----------|
| exp1 四档 × 3任务 成功率/Token/轮数表 | 5.1.3 节末尾"实战验证"小节 | 新增 |
| exp2 配置 A/B/C 命中率曲线 | 5.4.3 节末尾"实测数据"小节 | 新增 |
| exp2 配置 A/B/C 命中率数据 | 5.5.2 节"前缀变动导致 Cache 全量失效" | 经验值改为实测 |
| exp2 配置 D 数据 | 5.5.4 节经验二"时间精度降低到小时级别" | 经验值改为实测 |
| exp2 配置 E 数据 | 5.5.4 节经验一"工具 schema 顺序" | 经验值改为实测 |
| exp3 五对违反率对比 | 5.1.2 节"明确的禁令"段落后 | 新增 |

## 结果数据位置

所有原始数据写入各实验目录的 `results/` 子目录：

- `exp1_agents_md_length/results/results.json`
- `exp2_cache_stability/results/results.json`
- `exp3_prohibition_wording/results/results.json`

`results/` 目录通过根目录 `.gitignore` 的 `experiments/results/` 规则排除
出版本库（避免多次运行的数据污染 git 历史；如需长期归档把 json 手动复制
到别处）。

## 故障排查

- **UnicodeEncodeError**（Windows GBK 控制台）：设置 `PYTHONIOENCODING=utf-8`
- **API 连接失败**：检查 `.env` 中的 `OPENAI_BASE_URL` 和 `OPENAI_API_KEY`
- **pytest 无法找到**：实验一的成功验证依赖 pytest，确认 `python -m pytest --version` 有输出
- **Cache 命中率异常低（exp2 的 A 配置）**：可能是上一轮结束 > 5 分钟触发 TTL 过期；
  重新开始跑一次即可（DeepSeek 会自动重建缓存）

## 写作引用规范

章节里引用本目录时必须用相对路径（从仓库根起算），例如：

```markdown
本节的实验数据来自 `experiments/ch05/exp1_agents_md_length/`，
跑法见该目录的 `README.md`。
```

不要写绝对路径，不要写 `examples/...`（已从 examples 迁到 experiments）。
