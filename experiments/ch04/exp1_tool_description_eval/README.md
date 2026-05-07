# 工具描述 Eval — 使用说明

对`harness_py_pro`的6个内置工具做一次描述质量评测，输出 v1（当前）vs v2（优化版）的对比数据。产出同时用于书籍Ch4的4.5节和公众号文章配图。

## 前置要求

- Python 3.10+
- DeepSeek API key（去 [platform.deepseek.com](https://platform.deepseek.com) 申请，首次注册送¥10额度，本次eval消耗约¥3-5）
- `harness_py_pro` 模块可导入（已在本仓库`harness_py_pro/`下）

## 目录结构

```
experiments/ch04/exp1_tool_description_eval/
├── README.md                 ← 本文档
├── prepare_fixtures.py       ← Step 1: 生成测试用假项目
├── golden_set.jsonl          ← 100条测试任务
├── descriptions.py           ← v1 和 v2 的工具描述
├── eval_runner.py            ← Step 3/5: 核心评测脚本
├── report.py                 ← Step 4/6: 聚合结果生成markdown
└── eval_sandbox/             ← 自动生成，勿手动修改
```

## 完整流程（6步，全程约40分钟）

### Step 1：生成测试沙箱

```bash
cd D:/Working_Tools/Projects/harness-py-book/experiments/ch04/exp1_tool_description_eval/
python prepare_fixtures.py
```

**预期输出**：
```
[prepare_fixtures] 已生成 15 个fixture文件 → .../eval_sandbox
  - .gitignore
  - README.md
  - config.py
  ...
```

> **[SCREENSHOT-1]** 截这个终端输出，证明沙箱准备好了。

### Step 2：设置 API Key

**PowerShell（Windows推荐）**:
```powershell
$env:DEEPSEEK_API_KEY="sk-xxxxxxxx"
```

**Git Bash / Linux / macOS**:
```bash
export DEEPSEEK_API_KEY=sk-xxxxxxxx
```

验证设置成功：
```bash
python -c "import os; print('OK' if os.environ.get('DEEPSEEK_API_KEY') else 'MISSING')"
```

### Step 3：跑 v1 基线（当前描述）

```bash
python eval_runner.py --version v1 --out results_v1.json
```

**预期过程**（约20分钟）：
```
=== Tool Description Eval (version=v1) ===
  任务数: 100, seeds: [42, 43, 44], 总观测: 300
  沙箱:   .../eval_sandbox
  输出:   results_v1.json

[  1/300] rd001  seed=42 want=read_file    got=read_file      OK  ETA 1200s
[  2/300] rd001  seed=43 want=read_file    got=read_file      OK  ETA 1195s
...
[ 61/300] gr011  seed=42 want=grep_search  got=bash         FAIL  ETA  980s
...
```

> **[SCREENSHOT-2]** 截开头10行，证明跑起来了。
>
> **[SCREENSHOT-3]** 跑完后截总览（见下方"总览"部分），拿到 v1 的基线准确率。

**末尾输出示例**：
```
=== 总览 (version=v1) ===
  Tool Selection Accuracy: 67.3%  (202/300)
  Forbidden Hit Rate:      24.0%  (72/300)
  Args Correctness:        82.7%  (248/300)
  用时:                    1180s
  结果文件:                results_v1.json
```

### Step 4：生成 v1 详细报告（可选，验证数据）

```bash
python report.py results_v1.json > report_v1.md
```

打开`report_v1.md`查看详细拆解，能看到哪个category（如`read_confuse_bash`）准确率最低。

> **[SCREENSHOT-4]** 用VS Code / Typora预览`report_v1.md`，截"按Category拆解"那张表。

### Step 5：跑 v2（优化描述）

```bash
python eval_runner.py --version v2 --out results_v2.json
```

同样约20分钟。预期 v2 的 accuracy 会明显高于 v1。

> **[SCREENSHOT-5]** 同样截末尾"总览"部分，可以看到 v2 的提升。

### Step 6：生成 v1 vs v2 对比报告（核心产出）

```bash
python report.py results_v1.json results_v2.json > comparison.md
```

打开`comparison.md`，这是最终成品——直接可以：
- 贴进书籍Ch4的4.5节《工具层的度量与迭代》
- 改写成公众号文章的数据支撑部分

> **[SCREENSHOT-6]** 预览`comparison.md`，截"总体指标对比"和"按Category对比"两张表。这是整篇文章的核心图。

## 结果文件说明

| 文件 | 内容 | 用途 |
|------|------|------|
| `results_v1.json` | v1 每一条观测的原始数据 | 做自定义分析；公众号文章附件 |
| `results_v2.json` | v2 每一条观测的原始数据 | 同上 |
| `report_v1.md` | v1 详细分类+失败样例 | 书稿补充材料 |
| `comparison.md` | v1 vs v2 对比 | **书籍Ch4核心图表 + 公众号主图** |

## 调试模式

### 跑5条看看效果（耗时1分钟）

```bash
python eval_runner.py --version v1 --out smoke.json --limit 5 --seeds 1
```

如果这一步报错，先解决错误再跑完整eval。

### 只跑1个seed（耗时减半）

```bash
python eval_runner.py --version v1 --out results_v1_1seed.json --seeds 1
```

公众号文章可以用 1seed 数据（够明显），书籍建议用 3seeds（统计更严谨）。

## 常见问题

### Q: 报错 `[错误] 请设置环境变量 DEEPSEEK_API_KEY`

检查 Step 2 是否正确。PowerShell/Bash 环境变量只在当前窗口有效，换窗口要重新设。

### Q: 报错 `Rate limit exceeded`

加大 `--sleep` 间隔：
```bash
python eval_runner.py --version v1 --out results_v1.json --sleep 1.0
```

### Q: 中途中断怎么办？

目前不支持断点续跑（下次会做）。建议先用 `--limit 5` 跑一次验证流程，再跑完整的。

### Q: 想看某一条为什么失败

打开`results_v*.json`，按`id`搜索（如`"id": "rd016"`），`first_call`字段就是模型实际选了啥工具。

### Q: 我想改 v2 描述自己测

直接编辑 `descriptions.py` 里的 `V2_DESCRIPTIONS`，重跑 Step 5-6 即可。

## 文章建议

写成公众号文章时，推荐结构：

1. **引子**：大家都在讨论MCP和工具描述，但几乎没人实测过描述写得好不好
2. **方法论**：100条golden set + 3 seeds + pre_tool hook拦截（不真跑工具省钱）
3. **基线**：v1（常见的最小化描述）= 67%准确率（贴 [SCREENSHOT-3]）
4. **诊断**：拆类别看，bash被滥用最严重，24%forbidden hit（贴 [SCREENSHOT-4]）
5. **优化**：展示v2的6条改进描述，重点讲"DO NOT"的作用
6. **结果**：v2 = 89%，关键是 bash forbidden_hit 从24%降到5%（贴 [SCREENSHOT-6]）
7. **复现**：附上本目录GitHub链接，读者可自己跑

## 成本估算

- v1跑完：100任务 × 3seeds × ~2turns × ~3kinput+200output tokens ≈ 200万 input + 20万 output tokens
- DeepSeek价格：input ¥1/1M, output ¥2/1M
- 单次v1 ≈ ¥2.5，v1+v2合计 ≈ ¥5

如果用`--seeds 1`减半。

## 书籍Ch4收录建议

跑完后，把以下内容搬进Ch4的4.5节：

- `descriptions.py` 的 V1/V2 对照（代码块）
- `comparison.md` 的总体指标对比表（表1）
- `comparison.md` 的按Category对比表（表2）
- `comparison.md` 的Top混淆对比（表3）
- 6张截图中选3-4张作为配图
- 一段复盘：为什么"DO NOT"比"DO"效果好——小模型的attention在负向约束上权重更大（可引用[OpenAI Function Calling Best Practices, 2024](https://platform.openai.com/docs/guides/function-calling) 中类似观察）

这一节的核心价值是：这是你**自己在DeepSeek-V3上实测出来的数据**，不是转述他人结论。
