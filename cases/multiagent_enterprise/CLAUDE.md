# 多Agent企业级案例 — 项目Harness配置

## 案例概述

跨 Java + Python 的检验质控系统集成开发：为现有系统新增"智能报警分析"模块。
演示四Agent角色隔离编排：Architect、Java Developer、Python Developer、QA Engineer。

## Agent角色隔离规则

### 1. Architect Agent
- **工具权限：** 只读（read_file, grep_search, list_directory）
- **工作范围：** 全局可读，输出仅限 implementation_plan.md
- **禁止：** 不可创建或修改任何代码文件

### 2. Java Developer Agent
- **工具权限：** read_file, write_file, edit_file, bash(mvn compile, mvn test)
- **工作范围：** 限制在 `java_module/` 目录
- **禁止：** 不可修改 python_module/ 下的任何文件

### 3. Python Developer Agent
- **工具权限：** read_file, write_file, edit_file, bash(pytest, python)
- **工作范围：** 限制在 `python_module/` 目录
- **禁止：** 不可修改 java_module/ 下的任何文件

### 4. QA Engineer Agent
- **工具权限：** read_file, write_file, edit_file, grep_search, bash(mvn test, pytest)
- **工作范围：** 测试文件（java_module/src/test/, python_module/tests/）
- **禁止：** 不可修改业务代码（java_module/src/main/, python_module/app/）

## 接口契约管控

**核心规则：`spec/api_contract.yaml` 不可由单方修改。**

- 只有 Architect Agent 有权审批契约变更
- Java Developer 或 Python Developer 如需修改契约，须：
  1. 在其输出中标记 `[BLOCKED: 需要Architect审批契约变更]`
  2. 描述需要变更的内容和原因
  3. 等待 Architect 在下一轮审批

## 代码变更规则

- 每次代码变更后必须运行对应的验证命令：
  - Java 端：`mvn compile`（编译检查）
  - Python 端：`python -m py_compile <file>`（语法检查）
- Round 3（QA阶段）必须运行完整测试：
  - Java 端：`mvn test`
  - Python 端：`pytest -v`

## 文件结构

```
multiagent_enterprise/
├── CLAUDE.md                 # 本文件 — Harness 配置
├── TASK.md                   # 任务定义与编排流程
├── run.py                    # 四Agent编排执行脚本
├── verify.py                 # 验证脚本
├── spec/
│   ├── requirement.md        # 需求规格说明书
│   ├── api_contract.yaml     # OpenAPI 接口契约
│   └── architecture.md       # 现有架构说明
├── roles/
│   ├── architect.md          # Architect Agent 角色定义
│   ├── java_developer.md     # Java Developer Agent 角色定义
│   ├── python_developer.md   # Python Developer Agent 角色定义
│   └── qa_engineer.md        # QA Engineer Agent 角色定义
├── java_module/              # Java 端代码（模拟 H34 子模块）
│   ├── pom.xml
│   └── src/
└── python_module/            # Python 端代码（模拟 S37 子模块）
    ├── app/
    ├── tests/
    └── requirements.txt
```

## 编排顺序

1. **Round 1** — Architect 分析需求，输出 implementation_plan.md
2. **Round 2** — Java Dev + Python Dev 并行开发（可同时执行）
3. **Round 3** — QA Engineer 编写并执行测试
4. **Round 4** — 根据测试报告修复问题（按需分派给对应 Developer）
