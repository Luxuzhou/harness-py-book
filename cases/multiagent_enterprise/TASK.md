# 多Agent编排任务定义

## 任务目标

通过四Agent协作，完成诊疗临床路径系统"路径变异智能预警"模块的跨 Java/Python 集成开发。

---

## Round 1: 架构设计（Architect）

### 触发条件
编排开始时自动执行。

### 执行Agent
`architect`

### 输入文件
- `spec/requirement.md`
- `spec/api_contract.yaml`
- `spec/architecture.md`
- `java_module/` （代码骨架）
- `python_module/` （代码骨架）

### 期望行为
1. 通读全部 spec 文档和现有代码骨架
2. 分析 Java 端和 Python 端的职责边界
3. 审查 api_contract.yaml 的完整性
4. 输出 `implementation_plan.md`

### 输出文件
- `implementation_plan.md`（根目录下）

### 完成标准
- plan 包含 Java 端实施清单（至少5个文件的实现要点）
- plan 包含 Python 端实施清单（至少4个文件的实现要点）
- plan 包含接口契约关键约束
- plan 包含测试策略
- plan 包含风险与缓解措施

---

## Round 2: 并行开发（Java Dev + Python Dev）

### 触发条件
Round 1 完成后，`implementation_plan.md` 存在。

### 执行Agent
`java_developer` 和 `python_developer` **并行执行**。

### Java Developer

**输入：**
- `implementation_plan.md`（Java 端章节）
- `spec/api_contract.yaml`
- `java_module/` 现有骨架

**期望行为：**
1. 阅读 plan 中的 Java 端实施清单
2. 完善/新建所有必要的 Java 源文件
3. 确保 `mvn compile` 通过

**输出：**
- `java_module/` 下完整的实现代码
- 编译成功的确认

### Python Developer

**输入：**
- `implementation_plan.md`（Python 端章节）
- `spec/api_contract.yaml`
- `python_module/` 现有骨架

**期望行为：**
1. 阅读 plan 中的 Python 端实施清单
2. 完善/新建所有必要的 Python 源文件
3. 确保所有 .py 文件语法正确

**输出：**
- `python_module/` 下完整的实现代码
- 语法检查通过的确认

---

## Round 3: 测试验证（QA Engineer）

### 触发条件
Round 2 完成后（两个 Developer 都完成）。

### 执行Agent
`qa_engineer`

### 输入文件
- `implementation_plan.md`（测试策略章节）
- `spec/api_contract.yaml`
- `java_module/` 完成后的代码
- `python_module/` 完成后的代码

### 期望行为
1. 编写契约一致性测试（Python 端 Pydantic 模型 vs OpenAPI schema）
2. 编写 Python 端单元测试（算法核心函数、API 端点）
3. 编写 Java 端单元测试（Service 层、Controller 层）
4. 执行全部测试
5. 输出测试报告

### 输出文件
- `python_module/tests/test_contract_consistency.py`
- `python_module/tests/test_anomaly_analyzer.py`
- `java_module/src/test/java/com/example/cp/anomaly/AnomalyServiceTest.java`
- `java_module/src/test/java/com/example/cp/anomaly/AnomalyControllerTest.java`
- `test_report.md`（根目录下）

### 完成标准
- 至少编写 15 个测试用例
- 测试报告包含执行摘要和失败详情
- 契约一致性检查完成

---

## Round 4: 缺陷修复（按需）

### 触发条件
Round 3 的 `test_report.md` 中存在失败的测试。

### 执行Agent
根据失败测试的归属分派：
- Java 端 bug -> `java_developer`
- Python 端 bug -> `python_developer`
- 契约不一致 -> `architect`（审批后由对应 Developer 修改）

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
  name: "cp-anomaly-module"
  rounds:
    - name: "architecture-design"
      agents: ["architect"]
      parallel: false
    - name: "parallel-development"
      agents: ["java_developer", "python_developer"]
      parallel: true
    - name: "qa-verification"
      agents: ["qa_engineer"]
      parallel: false
    - name: "bug-fix"
      agents: ["java_developer", "python_developer"]
      parallel: true
      conditional: "test_report.md contains failures"
  
  artifacts:
    - name: "implementation_plan.md"
      producer: "architect"
      consumers: ["java_developer", "python_developer", "qa_engineer"]
    - name: "test_report.md"
      producer: "qa_engineer"
      consumers: ["java_developer", "python_developer"]
  
  constraints:
    - "api_contract.yaml is read-only for all agents except architect"
    - "java_developer cannot modify python_module/"
    - "python_developer cannot modify java_module/"
    - "qa_engineer cannot modify business code"
```
