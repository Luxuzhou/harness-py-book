# 跨项目多 Agent 编排任务定义

## 任务目标

通过四 Agent 协作，在两套真实业务代码（Java 端 + Python 端）之上完成"路径变异智能预警"模块的跨语言集成：

- Java 端：扩展第 9 章的 Spring Boot 项目（`cases/refactor_enterprise/target_project/`），新增 REST 客户端调用 Python 端的异常分析服务
- Python 端：扩展第 10 章的 FastAPI 服务（`cases/data_compliance/target_service/`），新增 REST 客户端回调 Java 端的异常规则同步接口
- 契约：双方通过 `spec/api_contract.yaml` 对齐，任何一方都不得单边改契约
- 测试：QA 端写跨契约一致性测试 + 两侧单元测试

---

## Round 1：架构设计（Architect）

### 触发条件
编排开始时自动执行。

### 执行 Agent
`Architect`

### 输入文件
- `spec/requirement.md`
- `spec/api_contract.yaml`
- `spec/architecture.md`
- `cases/refactor_enterprise/target_project/` — 第9章 Java 项目（只读）
- `cases/data_compliance/target_service/` — 第10章 Python 服务（只读）

### 期望行为
1. 通读全部 spec 文档
2. 抽样读两端代码的关键目录（Controller / Service / Routes）
3. 分析 Java 端与 Python 端各自需要新增/修改的点
4. 审查 `api_contract.yaml` 是否已覆盖本次集成
5. 输出 `implementation_plan.md`

### 输出文件
- `implementation_plan.md`（本案例目录下）

### 完成标准
- plan 包含 Java 端实施清单（至少 3 个文件的改动要点，落在第9章目录）
- plan 包含 Python 端实施清单（至少 3 个文件的改动要点，落在第10章目录）
- plan 包含接口契约关键约束
- plan 包含测试策略
- plan 包含风险与缓解措施

---

## Round 2：并行开发（Java Dev + Python Dev）

### 触发条件
Round 1 完成后，`implementation_plan.md` 存在。

### 执行 Agent
`JavaDeveloper` 与 `PythonDeveloper` **并行执行**（由 `parallel_groups={2: ['JavaDeveloper', 'PythonDeveloper']}` 声明）。

### Java Developer

**输入：**
- `implementation_plan.md`（Java 端章节）
- `spec/api_contract.yaml`
- `cases/refactor_enterprise/target_project/` 现有 Spring Boot 项目

**工作目录（由 Harness 的 cwd 强制锁定）：**
`cases/refactor_enterprise/target_project/`

**期望行为：**
1. 阅读 plan 中的 Java 端实施清单
2. 在 `src/main/java/com/example/cp/client/` 下新建或补全对 Python 服务的客户端
3. 确保 `mvn compile`（或 `javac`）通过

**输出：**
- `cases/refactor_enterprise/target_project/src/main/java/com/example/cp/client/*.java` 等新增/修改文件
- 编译成功的确认

### Python Developer

**输入：**
- `implementation_plan.md`（Python 端章节）
- `spec/api_contract.yaml`
- `cases/data_compliance/target_service/` 现有 FastAPI 服务

**工作目录（由 Harness 的 cwd 强制锁定）：**
`cases/data_compliance/target_service/`

**期望行为：**
1. 阅读 plan 中的 Python 端实施清单
2. 在 `app/clients/` 下新建或补全对 Java 服务的客户端（`java_api_client.py` 等）
3. 确保所有 .py 文件 `python -m py_compile` 通过
4. 必要时扩展 `app/api/routes/anomalies.py` 接收来自 Java 端的回调

**输出：**
- `cases/data_compliance/target_service/app/clients/*.py`
- 语法检查通过的确认

---

## Round 3：测试验证（QA Engineer）

### 触发条件
Round 2 完成后（两个 Developer 都完成）。

### 执行 Agent
`QAEngineer`

### 输入文件
- `implementation_plan.md`（测试策略章节）
- `spec/api_contract.yaml`
- 第9章 Java 项目完整代码（只读）
- 第10章 Python 服务完整代码（只读）

### 期望行为
1. 编写契约一致性测试（Python Pydantic 模型 vs OpenAPI schema；Java DTO vs OpenAPI schema）
2. 编写 Python 端单元测试（新增 client 的请求构造与错误处理）
3. 编写 Java 端单元测试（新增 client 的请求构造与错误处理）
4. 执行全部测试
5. 输出测试报告

### 输出文件
- 第10章服务下 `tests/test_contract_consistency.py`
- 第10章服务下 `tests/test_java_api_client.py`
- 第9章项目下 `src/test/java/com/example/cp/client/PythonServiceClientTest.java`
- `test_report.md`（本案例目录下）

### 完成标准
- 至少编写 15 个测试用例
- 测试报告包含执行摘要和失败详情
- 契约一致性检查完成

---

## Round 4：缺陷修复（按需）

### 触发条件
Round 3 的 `test_report.md` 中存在失败的测试。

### 执行 Agent
根据失败测试的归属分派：
- Java 端 bug → `JavaDeveloper`
- Python 端 bug → `PythonDeveloper`
- 契约不一致 → `Architect`（审批后由对应 Developer 修改）

### 输入文件
- `test_report.md`
- 失败测试的源代码

### 期望行为
1. 阅读测试报告中的失败项
2. 定位 root cause
3. 修复代码
4. 重新运行测试确认通过

### 完成标准
- 所有之前失败的测试现在通过
- 修复不引入新的失败

---

## 编排元数据

```yaml
orchestration:
  name: "cross-project-anomaly-module"
  anchors:
    java_project: "cases/refactor_enterprise/target_project/"
    python_service: "cases/data_compliance/target_service/"
  rounds:
    - name: "architecture-design"
      agents: ["Architect"]
      parallel: false
    - name: "parallel-development"
      agents: ["JavaDeveloper", "PythonDeveloper"]
      parallel: true
    - name: "qa-verification"
      agents: ["QAEngineer"]
      parallel: false
    - name: "bug-fix"
      agents: ["JavaDeveloper", "PythonDeveloper"]
      parallel: true
      conditional: "test_report.md contains failures"

  artifacts:
    - name: "implementation_plan.md"
      producer: "Architect"
      consumers: ["JavaDeveloper", "PythonDeveloper", "QAEngineer"]
    - name: "test_report.md"
      producer: "QAEngineer"
      consumers: ["JavaDeveloper", "PythonDeveloper"]

  constraints:
    - "api_contract.yaml is read-only for all agents except Architect"
    - "JavaDeveloper cannot modify cases/data_compliance/target_service/"
    - "PythonDeveloper cannot modify cases/refactor_enterprise/target_project/"
    - "QAEngineer cannot modify business code in either project"
```
