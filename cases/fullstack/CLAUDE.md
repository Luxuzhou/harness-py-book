# Multi-Agent Fullstack — Harness Configuration

## 项目信息
多Agent协作开发项目。三个Agent角色（Planner/Generator/Evaluator）迭代构建任务管理工具。

## 编排规则

### Agent隔离
- 每个Agent有独立的对话历史
- Agent之间只通过文件传递信息（plan.md, review.md, 代码文件）
- 禁止Agent直接访问其他Agent的内部状态

### 角色权限
- **Planner**：只读工具（read_file, grep_search, glob_search）
- **Generator**：全部工具（read_file, write_file, edit_file, bash, grep_search, glob_search）
- **Evaluator**：只读 + bash（仅限运行测试和检查命令）

### 迭代控制
- 最多3轮完整迭代
- 每轮中每个Agent最多15次工具调用
- 如果Evaluator给出PASS，立即终止迭代

### 文件约束
- 所有输出写入 `output/` 目录
- 不得修改 `TASK.md`、`CLAUDE.md`、`spec.md`
- 不得访问 `output/` 以外的项目文件（role定义除外）

## 质量标准
- 生成的代码必须是可直接运行的 Python 3.10+
- 仅使用标准库（json, argparse, pathlib, unittest/pytest）
- 测试必须可通过 `python -m pytest` 运行
