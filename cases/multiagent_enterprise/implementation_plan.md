# 实施计划 — 路径变异智能预警模块

## 1. 现状评估总结

### 1.1 Java 端（Ch8：`cases/refactor_enterprise/target_project/`）

| 组件 | 状态 | 说明 |
|------|------|------|
| `AnomalyController` | ✅ 已实现 | 3个端点（POST rules, GET rules/{id}, POST events） |
| `AnomalyService` | ✅ 已实现 | createRule, getRule, createEvent 三个方法 |
| `AnomalyRule` 实体 | ✅ 已实现 | 映射 anomaly_rule 表，MyBatis-Flex @Table |
| `AnomalyEvent` 实体 | ✅ 已实现 | 映射 anomaly_event 表 |
| `AnomalyRuleMapper` | ✅ 已实现 | findByTestItemId, existsByTestItemId |
| `AnomalyEventMapper` | ✅ 已实现 | findByTestItemId, findByTriggeredAtBetween |
| DTO 类（5个） | ✅ 已实现 | AnomalyRuleCreateRequest/Response, AnomalyEventCreateRequest/Response, DeviationPoint |
| `GlobalExceptionHandler` | ✅ 已实现 | 统一异常处理 |
| 单元测试 | ❌ 缺失 | Anomaly 相关无任何测试 |
| Jackson snake_case 配置 | ❌ 缺失 | application.yml 中未配置 property-naming-strategy |

### 1.2 Python 端（Ch9：`cases/data_compliance/target_service/`）

| 组件 | 状态 | 说明 |
|------|------|------|
| `schemas.py` 异常模型 | ✅ 已实现 | DeviationPoint, AnomalyRuleResponse, AnomalyEventCreateRequest/Response, AnomalyResult, HistoryAnalysis, AnomalySegment, ErrorResponse |
| `anomaly_analyzer.py` | ✅ 已实现 | AnomalyAnalyzer 类 + 核心算法纯函数 |
| `anomaly_rule_engine.py` | ✅ 已实现 | 6种规则类型的规则引擎（独立于本模块） |
| `anomaly_notifier.py` | ✅ 已实现 | 告警推送服务（独立于本模块） |
| `java_api_client.py` | ✅ 已实现 | get_anomaly_rule, create_anomaly_event |
| `routes/anomalies.py` | ✅ 已实现 | 异常规则与告警路由（独立于本模块） |
| 单元测试 `test_anomaly_analyzer.py` | ✅ 已实现 | 覆盖核心算法 + Golden 测试用例 |
| 契约测试 `test_contract_consistency.py` | ✅ 已实现 | 验证 Pydantic 模型与契约一致性 |

### 1.3 关键发现

1. **Java 端 Controller 响应格式与契约不一致**：Controller 返回 `Map<String, Object>` 包装格式（`{code, message, data}`），但 OpenAPI 契约要求直接返回 `AnomalyRuleResponse` / `AnomalyEventResponse` 对象。Python 端 `java_api_client.py` 的 `get_anomaly_rule` 方法直接 `AnomalyRuleResponse(**data)` 反序列化，如果 Java 端返回包装格式会导致解析失败。

2. **Jackson snake_case 配置缺失**：架构文档要求 JSON 序列化使用 snake_case，但 `application.yml` 中未配置 `spring.jackson.property-naming-strategy=SNAKE_CASE`。当前 Java DTO 使用 camelCase 字段名（如 `testItemId`），序列化后为 `testItemId` 而非 `test_item_id`。

3. **Python 端 `java_api_client.py` 的 `get_anomaly_rule` 方法**：直接对 Java 端返回的 JSON 调用 `AnomalyRuleResponse(**data)`，如果 Java 端返回的是 `{code, message, data}` 包装格式，会因字段不匹配而失败。

4. **Python 端 `analyze_history` 方法**：第 485 行 `parameters_source` 使用了 `"rule" if "rule" in dir() and rule else "custom"`，`dir()` 在运行时不会包含局部变量 `rule`，这是一个 bug。

---

## 2. Java 端实施清单

### 2.1 需要修改的文件

#### [J-1] `application.yml` — 添加 Jackson snake_case 配置

**文件路径**: `src/main/resources/application.yml`

**实现要点**:
1. 在 `spring.jackson` 下添加 `property-naming-strategy: SNAKE_CASE`
2. 确保不影响现有模块的 JSON 序列化行为
3. 验证：所有 DTO 的 JSON 输出字段名从 camelCase 变为 snake_case

```yaml
spring:
  jackson:
    property-naming-strategy: SNAKE_CASE
    date-format: yyyy-MM-dd HH:mm:ss
    time-zone: Asia/Shanghai
    default-property-inclusion: non_null
```

#### [J-2] `AnomalyController.java` — 修复响应格式以对齐契约

**文件路径**: `src/main/java/com/example/cp/controller/AnomalyController.java`

**实现要点**:
1. `createRule` 方法：返回 `ResponseEntity<AnomalyRuleResponse>` 而非 `ResponseEntity<Map<String, Object>>`
   - 成功时：`ResponseEntity.status(HttpStatus.CREATED).body(response)`
   - 冲突时：使用 `GlobalExceptionHandler` 统一处理 `IllegalStateException`，或返回 `ResponseEntity.status(HttpStatus.CONFLICT).body(new ErrorResponse(...))`
2. `getRule` 方法：返回 `ResponseEntity<AnomalyRuleResponse>` 而非 `ResponseEntity<Map<String, Object>>`
   - 成功时：`ResponseEntity.ok(response)`
   - 404 时：抛出 `CpBusinessException` 或返回 `ResponseEntity.notFound().build()`
3. `createEvent` 方法：返回 `ResponseEntity<AnomalyEventResponse>` 而非 `ResponseEntity<Map<String, Object>>`
   - 成功时：`ResponseEntity.status(HttpStatus.CREATED).body(response)`
   - 认证失败时：返回 401 状态码
4. 移除 `Map<String, Object>` 导入（如果不再使用）
5. 添加 `@ResponseStatus` 注解简化状态码声明

#### [J-3] `GlobalExceptionHandler.java` — 添加 ErrorResponse 响应格式

**文件路径**: `src/main/java/com/example/cp/exception/GlobalExceptionHandler.java`

**实现要点**:
1. 新增 `ErrorResponse` DTO 类（与契约一致，包含 `error_code`, `message`, `timestamp` 字段）
2. 修改 `buildErrorResponse` 方法返回 `ErrorResponse` 对象而非 `Map<String, Object>`
3. 确保 400/404/409/401 等错误响应格式与契约一致
4. 添加对 `IllegalStateException` 的处理（映射到 409 Conflict）

#### [J-4] 新增 `ErrorResponse.java` DTO

**文件路径**: `src/main/java/com/example/cp/dto/anomaly/ErrorResponse.java`

**实现要点**:
1. 字段：`errorCode` (String), `message` (String), `timestamp` (String)
2. 使用 Lombok `@Data`, `@Builder`, `@NoArgsConstructor`, `@AllArgsConstructor`
3. Jackson snake_case 配置生效后，`errorCode` 序列化为 `error_code`
4. 添加 `@Schema` 注解用于 OpenAPI 文档

#### [J-5] `AnomalyService.java` — 确认业务逻辑完整性

**文件路径**: `src/main/java/com/example/cp/service/anomaly/AnomalyService.java`

**实现要点**:
1. 确认 `createRule` 方法的事务回滚逻辑正确（`@Transactional(rollbackFor = Exception.class)`）
2. 确认 `createEvent` 方法中 `movingAverages` 和 `deviationPoints` 的 JSON 序列化逻辑
   - 当前使用 `toString()` 序列化 List，应改为使用 Jackson ObjectMapper 序列化
   - 或使用 `JSONUtil.toJsonStr()` 等工具方法
3. 添加日志记录：关键操作记录 INFO 日志，异常记录 ERROR 日志
4. 确认 `getRule` 方法返回 null 时 Controller 正确处理

#### [J-6] 新增单元测试

**文件路径**: `src/test/java/com/example/cp/service/anomaly/AnomalyServiceTest.java`

**实现要点**:
1. 使用 Mockito 模拟 `AnomalyRuleMapper` 和 `AnomalyEventMapper`
2. 测试 `createRule` 成功场景
3. 测试 `createRule` 重复规则冲突场景（抛出 IllegalStateException）
4. 测试 `getRule` 存在/不存在场景
5. 测试 `createEvent` 成功场景
6. 测试边界值：window_size=3/20, consecutive_count=2/10, threshold_multiplier=0.5/3.0

**文件路径**: `src/test/java/com/example/cp/controller/AnomalyControllerTest.java`

**实现要点**:
1. 使用 `@WebMvcTest` + MockMvc 测试 Controller 层
2. 测试 POST /api/v1/anomaly/rules 成功（201）
3. 测试 POST /api/v1/anomaly/rules 参数校验失败（400）
4. 测试 POST /api/v1/anomaly/rules 规则已存在（409）
5. 测试 GET /api/v1/anomaly/rules/{testItemId} 成功（200）
6. 测试 GET /api/v1/anomaly/rules/{testItemId} 不存在（404）
7. 测试 POST /api/v1/anomaly/events 成功（201）
8. 测试 POST /api/v1/anomaly/events Token 无效（401）
9. 测试 POST /api/v1/anomaly/events 参数校验失败（400）

### 2.2 注意事项

- **Jackson snake_case 配置影响范围**：修改 `property-naming-strategy` 会影响整个项目的 JSON 序列化。需要确认现有模块（如 CpDeviationController）是否依赖 camelCase 序列化。如果存在兼容性问题，考虑在 `AnomalyController` 上使用 `@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)` 局部配置。
- **响应格式变更影响**：Python 端 `java_api_client.py` 的 `get_anomaly_rule` 方法直接 `AnomalyRuleResponse(**data)` 反序列化。如果 Java 端返回格式从 `{code, message, data}` 改为直接返回 `AnomalyRuleResponse`，Python 端也需要相应调整。
- **参数校验**：`@Valid` 注解已启用，`GlobalExceptionHandler` 已处理 `MethodArgumentNotValidException`，无需额外配置。

---

## 3. Python 端实施清单

### 3.1 需要修改的文件

#### [P-1] `java_api_client.py` — 适配 Java 端响应格式

**文件路径**: `app/clients/java_api_client.py`

**实现要点**:
1. `get_anomaly_rule` 方法：根据 Java 端最终响应格式调整反序列化逻辑
   - 方案 A（推荐）：如果 Java 端直接返回 `AnomalyRuleResponse` JSON，保持 `AnomalyRuleResponse(**data)`
   - 方案 B：如果 Java 端返回 `{code, message, data}` 包装格式，改为 `AnomalyRuleResponse(**data["data"])`
2. `create_anomaly_event` 方法：同理适配
3. 添加响应格式日志（DEBUG 级别），便于调试
4. 确认 `_request` 方法中 404/401 异常处理逻辑正确

#### [P-2] `anomaly_analyzer.py` — 修复 `analyze_history` 中的 bug

**文件路径**: `app/services/anomaly_analyzer.py`

**实现要点**:
1. 修复第 485 行 `parameters_source` 的判断逻辑
   - 当前：`"rule" if "rule" in dir() and rule else "custom"`
   - 修复：使用一个布尔变量记录是否成功获取到规则
   ```python
   rule_fetched = False
   try:
       rule = await self._java_client.get_anomaly_rule(test_item_id)
       rule_fetched = True
       ...
   except JavaApiClientNotFoundError:
       ...
   ```
2. 确认 `analyze_realtime` 方法中异常处理逻辑完整
3. 确认 `compute_moving_averages` 和 `detect_deviationes` 纯函数无副作用

#### [P-3] `schemas.py` — 确认模型完整性

**文件路径**: `app/models/schemas.py`

**实现要点**:
1. 确认 `AnomalyRuleResponse` 字段与 OpenAPI 契约完全一致
2. 确认 `AnomalyEventCreateRequest` 字段与 OpenAPI 契约完全一致
3. 确认 `AnomalyEventResponse` 字段与 OpenAPI 契约完全一致
4. 确认 `DeviationPoint` 字段与 OpenAPI 契约完全一致
5. 确认 `ErrorResponse` 字段与 OpenAPI 契约完全一致
6. 当前模型已通过 `test_contract_consistency.py` 验证，无需修改

#### [P-4] 新增 API 路由（可选）

**文件路径**: `app/api/routes/anomaly_analysis.py`（新增）

**实现要点**:
1. 新增 `POST /api/v1/anomaly/analyze/realtime` 端点
   - 请求体：`test_item_id` + `measurements` 列表
   - 响应：`AnomalyResult`
2. 新增 `POST /api/v1/anomaly/analyze/history` 端点
   - 请求体：`test_item_id` + `start_date` + `end_date` + 可选 `custom_params`
   - 响应：`HistoryAnalysis`
3. 在 `main.py` 中注册新路由

#### [P-5] 新增单元测试

**文件路径**: `tests/test_anomaly_analyzer_integration.py`（新增）

**实现要点**:
1. 使用 `pytest-asyncio` 测试 `AnomalyAnalyzer` 类的 `analyze_realtime` 方法
2. Mock `JavaApiClient` 的 `get_anomaly_rule` 和 `create_anomaly_event` 方法
3. 测试正常流程：获取规则 → 计算 MA → 检测超限 → 上报事件
4. 测试规则不存在场景（返回未触发结果）
5. 测试 Java 端调用失败场景（优雅降级）
6. 测试 `analyze_history` 方法
7. 测试边界条件：空测量值序列、单值序列

### 3.2 注意事项

- **httpx 客户端配置**：`JavaApiClient` 已配置超时（connect=5s, read=10s）和重试（最多3次，间隔1s），符合需求文档要求。
- **异步调用**：`AnomalyAnalyzer.analyze_realtime` 和 `analyze_history` 都是 `async` 方法，测试需要使用 `pytest-asyncio`。
- **Mock 数据**：`_generate_mock_measurements` 使用 `numpy.random.default_rng(seed=hash(...))` 保证可复现性，适合测试。

---

## 4. 接口契约关键约束

### 4.1 字段命名规范

| 规范 | 说明 |
|------|------|
| Java 代码 | camelCase（如 `testItemId`） |
| JSON 序列化 | snake_case（如 `test_item_id`） |
| Python 代码 | snake_case（如 `test_item_id`） |
| 配置方式 | Java 端通过 `spring.jackson.property-naming-strategy=SNAKE_CASE` |

### 4.2 必填/可选字段

| Schema | 必填字段 | 可选字段 |
|--------|----------|----------|
| `AnomalyRuleCreateRequest` | test_item_id, test_item_name, target_value, sd_value | window_size(default=5), consecutive_count(default=3), threshold_multiplier(default=1.5), enabled(default=true) |
| `AnomalyRuleResponse` | 全部字段 | - |
| `AnomalyEventCreateRequest` | rule_id, test_item_id, triggered_at, severity | moving_averages, deviation_points, message |
| `AnomalyEventResponse` | 全部字段 | - |
| `DeviationPoint` | 全部字段 | - |
| `ErrorResponse` | error_code, message | timestamp |

### 4.3 错误码定义

| HTTP 状态码 | error_code | 场景 |
|-------------|------------|------|
| 400 | VALIDATION_FAILED | 参数校验失败 |
| 401 | AUTH_FAILED | Service Token 无效 |
| 404 | RULE_NOT_FOUND | 规则不存在 |
| 409 | RULE_ALREADY_EXISTS | 规则已存在 |
| 500 | SYSTEM_ERROR | 系统内部错误 |

### 4.4 认证要求

- 接口：`POST /api/v1/anomaly/events`
- Header：`X-Service-Token`
- 默认值：`default-service-token`
- 配置方式：Java 端 `cp.service.token`，Python 端 `SERVICE_TOKEN`

---

## 5. 测试策略

### 5.1 Java 端单元测试清单

| 测试类 | 测试方法 | 覆盖场景 |
|--------|----------|----------|
| `AnomalyServiceTest` | `createRule_success` | 正常创建规则 |
| | `createRule_duplicate_throws` | 重复规则冲突 |
| | `getRule_found` | 查询存在的规则 |
| | `getRule_notFound` | 查询不存在的规则 |
| | `createEvent_success` | 正常记录事件 |
| | `createEvent_withDeviationPoints` | 带超限点的事件 |
| `AnomalyControllerTest` | `createRule_201` | 创建成功 |
| | `createRule_400` | 参数校验失败 |
| | `createRule_409` | 规则已存在 |
| | `getRule_200` | 查询成功 |
| | `getRule_404` | 规则不存在 |
| | `createEvent_201` | 事件记录成功 |
| | `createEvent_401` | Token 无效 |
| | `createEvent_400` | 参数校验失败 |

### 5.2 Python 端单元测试清单

| 测试类 | 测试方法 | 覆盖场景 |
|--------|----------|----------|
| `TestComputeMovingAverages` | ✅ 已实现 | 6个测试用例 |
| `TestDetectDeviations` | ✅ 已实现 | 6个测试用例 |
| `TestConsecutiveSegments` | ✅ 已实现 | 4个测试用例 |
| `TestDetermineSeverity` | ✅ 已实现 | 2个测试用例 |
| `TestGoldenCases` | ✅ 已实现 | 4个 Golden 测试用例 |
| `TestAnomalyAnalyzerIntegration`（新增） | `analyze_realtime_triggered` | 实时分析触发异常 |
| | `analyze_realtime_not_triggered` | 实时分析未触发 |
| | `analyze_realtime_no_rule` | 规则不存在 |
| | `analyze_realtime_java_error` | Java 端调用失败 |
| | `analyze_history_with_params` | 历史分析带自定义参数 |
| | `analyze_history_default_params` | 历史分析使用默认参数 |

### 5.3 契约一致性验证方案

| 验证项 | 验证方式 | 负责方 |
|--------|----------|--------|
| Java 端 API 响应格式 | 集成测试 + OpenAPI 契约校验 | QA Engineer |
| Python 端 Pydantic 模型字段 | `test_contract_consistency.py` ✅ 已实现 | QA Engineer |
| 字段命名 snake_case | 集成测试验证 JSON 字段名 | QA Engineer |
| 错误码一致性 | 集成测试验证错误响应 | QA Engineer |

### 5.4 集成测试清单

| 测试场景 | 描述 | 验证点 |
|----------|------|--------|
| 端到端流程 | Python 调用 Java 获取规则 → 计算 → 上报事件 | 完整链路 |
| 规则不存在 | Python 查询不存在的规则 | 404 处理 |
| 认证失败 | Python 使用错误 Token 调用 Java | 401 处理 |
| 参数越界 | Java 端接收 window_size=1 | 400 校验 |
| 并发创建 | 同时创建同一诊疗项目的规则 | 409 冲突 |

---

## 6. 风险与缓解

### 6.1 已识别的技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| Jackson snake_case 配置影响现有模块 | 现有 API 响应格式变化 | 中 | 先在 `AnomalyController` 上使用 `@JsonNaming` 局部配置，验证后再全局启用 |
| Java 端响应格式变更导致 Python 端解析失败 | 集成测试失败 | 高 | 两端开发完成后立即运行集成测试，QA Engineer 负责验证 |
| `analyze_history` 中 `dir()` bug 导致 `parameters_source` 始终为 "custom" | 统计摘要字段错误 | 高 | Python Developer 修复该 bug |
| 无数据库环境导致 Java 端测试无法运行 | 单元测试覆盖率不足 | 中 | 使用 H2 内存数据库或 Mock Mapper 进行单元测试 |
| Python 端 `java_api_client.py` 的 `get_anomaly_rule` 反序列化失败 | 实时分析功能不可用 | 高 | 两端约定响应格式后，Python 端适配反序列化逻辑 |

### 6.2 缓解措施

1. **契约先行**：Java Developer 和 Python Developer 在开始编码前，先确认接口契约的响应格式
2. **分步验证**：
   - Java 端：`mvn compile` → `mvn test` → 手动测试 API
   - Python 端：`python -m py_compile` → `pytest` → 手动测试 API
3. **集成测试**：QA Engineer 在 Round 3 运行端到端集成测试
4. **回滚方案**：如果 Jackson snake_case 配置导致兼容性问题，回退到局部 `@JsonNaming` 配置

---

## 7. 实施顺序建议

```
Round 2 并行开发：
  Java Developer:
    1. [J-1] application.yml 添加 snake_case 配置
    2. [J-4] 新增 ErrorResponse.java
    3. [J-3] 修改 GlobalExceptionHandler
    4. [J-2] 修改 AnomalyController 响应格式
    5. [J-5] 确认 AnomalyService 逻辑
    6. [J-6] 新增单元测试

  Python Developer:
    1. [P-3] 确认 schemas.py 模型完整性
    2. [P-2] 修复 analyze_history bug
    3. [P-1] 适配 java_api_client.py
    4. [P-4] 新增 API 路由（可选）
    5. [P-5] 新增单元测试

Round 3 QA 验证：
  QA Engineer:
    1. 运行 Java 端 mvn test
    2. 运行 Python 端 pytest
    3. 运行契约一致性测试
    4. 运行集成测试
    5. 输出 test_report.md
```
