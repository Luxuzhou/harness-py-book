# 智能报警分析模块 — 需求规格说明书

## 1. 背景

### 1.1 项目概述

某三甲医院检验科运行两套质控系统：
- **H34**（Java / Spring Boot）：检验质控规则管理平台，负责规则配置、报警事件存储、与LIS对接
- **S37**（Python / FastAPI）：质控数据分析引擎，负责统计计算、趋势分析、智能判定

两套系统通过 REST API 交互，Java 端负责数据持久化与流程管控，Python 端负责算法运算。

### 1.2 现状痛点

当前质控系统仅支持 Westgard 规则等经典判定逻辑，缺乏基于移动均值（Moving Average）的
智能报警能力。临床反馈：
- 试剂批号切换后，结果出现缓慢漂移，传统规则无法及时捕获
- 质控品接近过期时的系统性偏移，需要更灵敏的检测手段
- 希望能自定义报警灵敏度，不同检验项目可以有不同的判定参数

### 1.3 建设目标

新增"智能报警分析"模块，实现：
1. 基于移动均值的智能报警判定
2. 可配置的报警规则参数
3. 报警事件的结构化存储与历史追溯
4. 报警趋势的统计分析

---

## 2. 业务需求

### 2.1 核心业务规则

**移动均值报警判定逻辑：**

给定一个质控检测序列 `[x1, x2, ..., xn]`，计算窗口大小为 `W` 的移动均值：

```
MA(i) = mean(x[i-W+1], x[i-W+2], ..., x[i])
```

当连续 `N` 个移动均值超过控制限（`target +/- threshold`）时，触发智能报警。

**参数定义：**
| 参数 | 含义 | 默认值 | 范围 |
|------|------|--------|------|
| window_size | 移动均值窗口大小 | 5 | 3~20 |
| consecutive_count | 连续超限次数 | 3 | 2~10 |
| threshold_multiplier | 控制限倍数（相对于SD） | 1.5 | 0.5~3.0 |

### 2.2 用户场景

**场景一：配置报警规则**
1. 质控管理员在 H34 系统中，为某个检验项目（如"血糖 GLU"）创建报警规则
2. 设置窗口大小=5，连续超限次数=3，阈值倍数=1.5
3. 设置启用状态为"启用"
4. 系统保存规则并同步到 S37 分析引擎

**场景二：自动报警判定**
1. S37 系统定时（或被触发）获取最新的质控数据
2. 按照报警规则计算移动均值
3. 判定是否触发报警条件
4. 如果触发，通过 REST API 向 H34 报告报警事件
5. H34 存储报警事件，推送通知给相关人员

**场景三：历史分析**
1. 用户在 S37 系统中查看某个检验项目的报警历史
2. 系统展示移动均值趋势图数据（返回JSON，前端渲染）
3. 用户可以调整参数，进行"回测"分析

---

## 3. 接口设计

### 3.1 Java端需要实现的API（3个端点）

#### POST /api/v1/alarm/rules — 创建报警规则
- 请求体：AlarmRuleDto（检验项目ID、窗口大小、连续次数、阈值倍数、启用状态）
- 响应：创建成功的规则（含自动生成的ID和时间戳）
- 校验：窗口大小3~20，连续次数2~10，阈值倍数0.5~3.0

#### GET /api/v1/alarm/rules/{testItemId} — 查询报警规则
- 路径参数：testItemId（检验项目ID）
- 响应：该检验项目的报警规则（如果存在）
- 不存在时返回 404

#### POST /api/v1/alarm/events — 记录报警事件
- 请求体：AlarmEventDto（规则ID、检验项目ID、触发时间、移动均值序列、严重程度）
- 响应：存储成功的报警事件（含ID）
- 此接口由 S37 的 Python 端调用

### 3.2 Python端需要实现的服务方法（2个）

#### analyze_realtime(test_item_id, measurements) -> AlarmResult
- 输入：检验项目ID + 最新的测量值序列
- 逻辑：
  1. 调用 Java 端 GET /api/v1/alarm/rules/{testItemId} 获取报警规则
  2. 计算移动均值序列
  3. 判定是否连续N次超过控制限
  4. 如果触发报警，调用 Java 端 POST /api/v1/alarm/events 记录
- 输出：AlarmResult（是否报警、移动均值序列、超限点位）

#### analyze_history(test_item_id, start_date, end_date, custom_params) -> HistoryAnalysis
- 输入：检验项目ID + 时间范围 + 可选的自定义参数（用于回测）
- 逻辑：
  1. 从数据源获取历史测量数据（本案例中用mock数据）
  2. 使用指定参数（或默认规则参数）计算移动均值序列
  3. 标记所有超限点和报警区段
- 输出：HistoryAnalysis（移动均值序列、超限点列表、报警区段列表、统计摘要）

---

## 4. 数据库变更

### 4.1 Java端新增2张表

#### alarm_rule 表
```sql
CREATE TABLE alarm_rule (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    test_item_id    VARCHAR(64)   NOT NULL COMMENT '检验项目ID',
    test_item_name  VARCHAR(128)  NOT NULL COMMENT '检验项目名称',
    window_size     INT           NOT NULL DEFAULT 5 COMMENT '移动均值窗口大小',
    consecutive_count INT         NOT NULL DEFAULT 3 COMMENT '连续超限判定次数',
    threshold_multiplier DECIMAL(4,2) NOT NULL DEFAULT 1.50 COMMENT '控制限倍数(相对SD)',
    target_value    DECIMAL(10,4) COMMENT '目标值(靶值)',
    sd_value        DECIMAL(10,4) COMMENT '标准差',
    enabled         TINYINT(1)    NOT NULL DEFAULT 1 COMMENT '是否启用',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_test_item (test_item_id)
) COMMENT='智能报警规则配置';
```

#### alarm_event 表
```sql
CREATE TABLE alarm_event (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    rule_id         BIGINT        NOT NULL COMMENT '关联的报警规则ID',
    test_item_id    VARCHAR(64)   NOT NULL COMMENT '检验项目ID',
    triggered_at    DATETIME      NOT NULL COMMENT '报警触发时间',
    severity        VARCHAR(16)   NOT NULL DEFAULT 'WARNING' COMMENT '严重程度: WARNING/CRITICAL',
    moving_averages TEXT          COMMENT '触发时的移动均值序列(JSON数组)',
    breach_points   TEXT          COMMENT '超限点位信息(JSON数组)',
    message         VARCHAR(512)  COMMENT '报警描述信息',
    acknowledged    TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否已确认',
    acknowledged_by VARCHAR(64)   COMMENT '确认人',
    acknowledged_at DATETIME      COMMENT '确认时间',
    created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_test_item (test_item_id),
    INDEX idx_triggered (triggered_at),
    INDEX idx_rule (rule_id)
) COMMENT='报警事件记录';
```

---

## 5. 接口契约

详见 `api_contract.yaml`，定义了 Java 端暴露给 Python 端的完整 OpenAPI 3.0 规范。

关键约束：
- 接口契约由 Architect Agent 审定，Java Developer 和 Python Developer 不可单方面修改
- 任何契约变更需提交 PR 由 Architect 审批
- 请求/响应的字段命名统一使用 snake_case（Java 端通过 Jackson 配置映射）

---

## 6. 非功能需求

### 6.1 性能要求
| 指标 | 要求 |
|------|------|
| 报警规则查询延迟 | P99 < 50ms |
| 实时分析延迟 | P99 < 200ms（含与Java端的两次REST调用） |
| 历史分析延迟 | P99 < 2s（365天数据量） |
| 并发支持 | 100个并发分析请求 |

### 6.2 可靠性要求
- 报警事件不可丢失，Java 端写入采用事务保证
- Python 端调用 Java 端失败时，记录本地日志并重试（最多3次，间隔1s）
- 报警规则缓存 TTL=60s，避免频繁查询数据库

### 6.3 安全要求
- API 间调用使用内部 Service Token 认证（本案例简化为 Header: X-Service-Token）
- 报警规则的增删改需要审计日志

### 6.4 可观测性
- Java 端：关键操作记录 INFO 日志，异常记录 ERROR 日志
- Python 端：分析过程记录 DEBUG 日志，报警触发记录 WARNING 日志
- 两端通过 traceId 串联调用链路

---

## 7. 测试策略

### 7.1 单元测试
- Java 端：Controller 层 MockMvc 测试、Service 层 Mock 测试
- Python 端：算法核心逻辑 pytest 测试、API endpoint 测试

### 7.2 集成测试
- 契约一致性测试：验证 Java 端 API 的请求/响应格式与 OpenAPI 契约一致
- 端到端流程测试：模拟 Python 调用 Java API 的完整流程

### 7.3 回归测试
- 已知的报警场景 golden test case：
  - 正常序列（不报警）
  - 渐变漂移序列（应报警）
  - 突变后恢复序列（不报警）
  - 边界条件（恰好N-1次超限，不报警）

---

## 8. 交付里程碑

| 阶段 | 交付物 | 负责Agent |
|------|--------|-----------|
| Round 1 | implementation_plan.md | Architect |
| Round 2 | Java端3个API + Python端2个服务方法 | Java Dev + Python Dev（并行） |
| Round 3 | 单元测试 + 集成测试 + 契约验证 | QA Engineer |
| Round 4 | 修复测试发现的问题 | Java Dev / Python Dev |
