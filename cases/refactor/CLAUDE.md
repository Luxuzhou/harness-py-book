# Refactor Project — Harness Configuration

## 项目信息
这是一个遗留的库存管理系统，需要进行安全重构。

## 约束规则

### 安全约束
- 禁止执行 `rm -rf`、`del /f` 或任何批量删除命令
- 禁止修改 `.git/` 目录
- 禁止访问 `target_project/` 目录之外的文件

### 重构约束
- **先测试后重构**：在修改任何业务代码前，必须先运行现有测试确认全部通过
- **小步前进**：每次只做一个重构操作，做完立即运行测试
- **不改行为**：重构不能改变任何公开方法的输入输出契约
- **不删接口**：即使方法已废弃，也只标记 `@deprecated`，不删除

### 工具使用规则
- 前3轮只使用 `read_file`、`grep_search`、`glob_search` 理解代码
- 第4轮起可使用 `write_file`、`edit_file`
- `bash` 仅用于运行测试（`python -m pytest`），不用于其他命令

### 质量要求
- 新代码必须有 type hints
- 每个新文件必须有模块级 docstring
- 类和公开方法必须有 docstring
