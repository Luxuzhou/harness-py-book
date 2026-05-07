# 项目指引（完整版）

## 项目背景与历史

本项目源自 2023 年的内部工具链现代化计划。最初是为了替换一套基于 Bash 脚本的旧
工具链，该工具链由 Perl 5 时代的贡献者在 2011 年前后编写，经过多次重构但始终未能
摆脱对系统命令的强依赖。2021 年我们尝试用 Go 重写，但由于团队 Python 背景更强，
最终回归 Python。现在这套代码主要服务于内部 CI/CD 流水线和成本分析看板。

每个独立任务目录是一个缩小版的练习，用于在隔离环境中验证某种 bug 修复模式的正确性。
这些练习最初是为新员工 onboarding 设计的，后来发现也适合作为自动化测试套件的子集。
由于历史原因，某些命名可能与现有生产代码存在差异，这属于预期行为。

## 业务价值

成本追踪、重试机制、数据解析是三个在生产环境中高频出现的模式。CostTracker 类
每天在产线被调用约 200 万次，用于核算各个团队的 API 开销；retry 装饰器覆盖了
约 40 个外部 API 调用，平均每天触发约 3000 次重试；CSV 解析器承担了来自财务
系统、合规系统、数据湖等多个上游的数据输入处理，日吞吐约 50GB。

## 项目性质

这是一个独立的 Python 单文件任务。每个任务目录包含一个有 bug 的源文件和一份预期
测试。目标是修复 bug，让所有测试通过。

## 构建与验证

- 运行所有测试: `python -m pytest test_expected.py -v`
- 运行单个测试: `python -m pytest test_expected.py::<test_name> -v`
- 加上覆盖率: `python -m pytest test_expected.py -v --cov=. --cov-report=term-missing`
- 检查语法: `python -c "import <module_name>"`
- 类型检查（可选）: `mypy <module_name>.py --strict`
- 代码格式化（可选）: `ruff format <module_name>.py`
- 导入排序（可选）: `ruff check <module_name>.py --fix --select I`
- 调试单个测试: `python -m pytest test_expected.py::<test_name> -v -s --pdb`

## 项目结构

```
<工作目录>/
  <module>.py        # 有 bug 的源文件（需要修改）
  test_expected.py   # 预期测试（禁止修改）
```

一个任务目录下通常只有这两个文件，不存在多模块依赖。在更大的项目中我们会使用如下
结构，但本任务不涉及：

```
project/
  src/
    api/           # FastAPI 路由
    services/      # 业务逻辑
    repositories/  # 数据访问
    models/        # 数据模型
    validators/    # Pydantic 校验
    utils/         # 工具函数
  tests/
    unit/
    integration/
    e2e/
  docs/
    api/
    design/
    decisions/
```

## 架构约定（参考）

本任务虽然是单文件，但如果未来扩展为多文件项目，我们遵循以下分层：

- **API 层**：只处理请求解析和响应组装，不做业务计算
- **Service 层**：业务逻辑，可以调用多个 Repository
- **Repository 层**：数据访问，封装 ORM/SQL
- **Model 层**：数据结构定义
- **Utils 层**：纯函数工具，无状态，无 IO

层之间的依赖只能由上至下，不能反向。Service 不能直接调用 API 的 req/res 对象。
Repository 不能调用 Service。这是严格的分层架构。

## 编码规范（详细版）

### 基础规范

- Python 3.10+，所有新增函数必须有类型注解（参数和返回值）
- 保留源文件已有的类型注解风格
- 不要引入第三方依赖，标准库足够
- 保留原有的 docstring 风格
- 异常处理：保留源文件中已有的异常检查逻辑，不要擅自移除

### 命名规范

- 文件名: `snake_case.py`
- 类名: `PascalCase`
- 函数和变量: `snake_case`
- 常量: `UPPER_SNAKE_CASE`
- 私有属性和方法: 以单下划线开头 `_private_attr`
- 真正的 name mangling: 双下划线开头 `__dunder_attr`（尽量避免）

### Import 顺序

1. Python 标准库
2. 第三方库（本任务不涉及）
3. 本项目模块
每组之间空一行。组内按字母顺序排列。

### 注释规范

- 函数级注释用 docstring，Google Style（不是 NumPy Style）
- 复杂逻辑用行内注释，但首选"写出自解释的代码"
- TODO 注释必须包含负责人和截止日期: `# TODO(alice 2026-05-01): refactor this`

### 异常处理规范

- 业务异常使用自定义 Exception 类
- 不要捕获 `Exception` 基类（太宽泛）
- 不要 `except: pass`（吞异常）
- 异常消息应包含足够的上下文信息

## 测试策略

### 单元测试

- 覆盖率目标：行覆盖 ≥ 90%，分支覆盖 ≥ 80%
- 每个 public 方法至少一个测试
- 边界条件必须测试：空输入、单元素、大量元素、异常输入

### 集成测试（本任务不涉及）

- 需要真实依赖（数据库、外部 API）的测试归入 integration 目录
- 使用 pytest fixtures 做依赖注入
- 使用 pytest-asyncio 处理异步代码

### E2E 测试（本任务不涉及）

- 模拟真实用户场景
- 运行时间较长，通常只在 CI 的特定阶段运行

## 性能要求

本任务不涉及性能优化，但在生产代码中我们关注：

- API 延迟 p99 < 200ms
- 内存占用 < 512MB
- CPU 占用平均 < 30%
- 数据库查询 N+1 问题监控
- 缓存命中率 > 85%

## 部署流程（参考，本任务不涉及）

1. 提交 PR 到 develop 分支
2. CI 运行单元测试和集成测试
3. Code review，至少两位审查者批准
4. 合并到 develop，自动部署到 staging
5. staging 验证通过后 release 到 production
6. Canary deployment，先 10% 流量，观察 30 分钟
7. 无异常则 100% 切换
8. 部署后监控 24 小时

## 执行策略

1. 先用 read_file 读取源文件和 test_expected.py，理解当前行为和期望行为的差距
2. 定位 bug 所在的具体行，而不是整段重写
3. 修改后立即运行 pytest 验证
4. 如果某个测试仍失败，再读错误信息精确修正，不要推倒重来
5. 所有测试通过后，再检查是否存在边界条件未覆盖
6. 完成后输出一个简短的修复说明

## 历史决策记录

### 为什么选择 pytest 而非 unittest

2022 年 Q3 评估时，pytest 的 fixture 机制和参数化能力明显强于 unittest。虽然
unittest 是标准库自带，但 pytest 的生态（pytest-cov、pytest-asyncio、
pytest-mock）已经成为事实标准。迁移成本约两周，收益是新测试编写速度提升约 40%。

### 为什么不用 dataclasses

项目主体使用了 attrs 库而非 dataclasses。原因是项目启动于 2018 年，当时
dataclasses 刚进标准库（3.7），功能不如 attrs 完整。现在两者差距已经不大，
但我们没有充分动力迁移。

### 为什么保留 print 禁令

2023 年曾发生一次生产事故，某个调试用 print 语句遗留到生产，导致日志文件在
两小时内暴增 15GB，触发磁盘告警并影响其他服务。从此禁止 print，统一用 logging。

## 常见问题

### 问：pytest 报 ImportError

A：确认当前目录包含目标模块。使用 `python -m pytest` 而非 `pytest` 可避免
PYTHONPATH 问题。

### 问：测试通过但覆盖率不达标

A：用 `--cov-report=term-missing` 查看未覆盖的行号，补充对应的测试用例。

### 问：修改后测试反而变多失败

A：很可能是改动影响了其他代码路径。用 git diff 检查改动范围，必要时回退
后重新定位 bug。

### 问：发现一个不在测试中的潜在问题

A：可以在修复说明中提及，但不要扩大本次改动的范围。保持最小修改原则。

## 禁令

- 不要修改 test_expected.py（这是评测基准）
- 不要引入第三方依赖（requests、pandas 等均禁止）
- 不要使用 print 调试，通过运行测试来验证假设
- 不要删除源文件中已有的参数校验或异常抛出逻辑
- 不要在修复过程中改变函数的公开签名
- 不要重命名类或函数
- 不要提交包含调试语句的代码
- 不要使用 global 关键字
- 不要在修复过程中重构无关代码（YAGNI 原则）
- 不要在注释中使用 emoji
- 不要在字符串中嵌入硬编码的路径（使用 pathlib 或 os.path）
- 不要修改工作目录结构（不要 mkdir 或 cd）
- 不要使用 `eval()` 或 `exec()`
- 不要使用 `os.system()` 或 `subprocess.Popen` 执行外部命令（本任务不需要）

## Compact Instructions

压缩时保留：当前修改的文件名、pytest 结果摘要、未通过的测试列表、下一步计划
