# Case 3: 多Agent协作全栈开发

## 背景

用三个Agent角色协作，从一句话需求开始，构建一个完整的任务管理Web应用。

这个案例演示Harness Engineering的终极形态：多Agent编排。每个Agent有不同的角色、工具权限和评判标准，通过迭代协作收敛到一个可运行的产品。

## 需求（一句话）

> 构建一个命令行任务管理工具，支持添加、列出、完成、删除任务，数据持久化到本地JSON文件。

## 三角色设计

### Planner（规划者）
- **职责**：将需求分解为具体的技术方案和文件清单
- **工具权限**：只读（read_file, grep_search, glob_search）
- **输出**：`plan.md` — 包含架构设计、文件清单、接口定义、测试用例设计

### Generator（生成者）
- **职责**：按照Plan编写全部代码和测试
- **工具权限**：全部（read/write/edit/bash/grep/glob）
- **输入**：Planner的 `plan.md`
- **输出**：完整的项目代码 + 测试

### Evaluator（评审者）
- **职责**：审查代码质量，运行测试，给出改进意见
- **工具权限**：只读 + bash（运行测试）
- **输入**：Generator生成的代码
- **输出**：`review.md` — 评审意见 + 通过/不通过判定

## 协作流程

```
Round 1:
  Planner → plan.md
  Generator → (reads plan.md) → code + tests
  Evaluator → (reads code) → review.md [PASS/FAIL + feedback]

Round 2 (if FAIL):
  Generator → (reads review.md) → fixes code
  Evaluator → (reads fixed code) → review.md [PASS/FAIL]

Round 3 (if still FAIL):
  Planner → (reads review.md) → revised plan.md
  Generator → (reads revised plan) → rewrites code
  Evaluator → final review
```

最多3轮迭代。如果3轮后仍未通过，输出当前最佳版本 + 未解决问题清单。

## 评审标准（Evaluator使用）

### 功能完整性（40分）
- [ ] 添加任务（10分）
- [ ] 列出所有任务（10分）
- [ ] 标记任务完成（10分）
- [ ] 删除任务（10分）

### 代码质量（30分）
- [ ] 代码有 type hints（10分）
- [ ] 有 docstring（5分）
- [ ] 无硬编码路径（5分）
- [ ] 错误处理完善（10分）

### 测试覆盖（30分）
- [ ] 测试存在且可运行（10分）
- [ ] 覆盖全部4个功能（10分）
- [ ] 边界条件测试（空列表、不存在的ID等）（10分）

**通过阈值：70分**

## 生成目录结构

```
output/
├── task_cli.py          ← 主程序
├── task_store.py        ← 数据持久化层
├── tests/
│   └── test_task_cli.py ← 测试
├── plan.md              ← Planner输出
└── review.md            ← Evaluator输出
```

## 验收标准

- [ ] `python output/task_cli.py add "Buy milk"` 成功添加任务
- [ ] `python output/task_cli.py list` 显示任务列表
- [ ] `python output/task_cli.py done 1` 标记完成
- [ ] `python output/task_cli.py delete 1` 删除任务
- [ ] `python -m pytest output/tests/` 全部通过
- [ ] Evaluator评分 ≥ 70分
- [ ] 经历了至少1轮 Planner→Generator→Evaluator 完整循环
