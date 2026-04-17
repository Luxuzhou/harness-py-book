# 遗留系统重构案例 — 项目 Harness 配置

## 案例定位

本案例展示 Harness 如何引导 Agent 对真实规模的企业级 Java 项目做"不破坏对外行为"的结构性重构。
`target_project/` 参照真实生产临床路径管理系统脱敏改写，保留了企业级项目的架构复杂度：
Controller / Service / DAO / DTO / Config / Enum / Exception / Mapper 八层分工完整。

## 重构规则（CLAUDE.md 承担的行为约束）

### 范围纪律

- 所有修改必须限定在 `target_project/src/main/java/com/example/cp/service/` 及其子目录
- 不得修改 Controller 层的方法签名、参数、返回类型
- 不得修改 `mapper/`、`model/`、`dto/`、`enum/` 下的任何现有类
- 不得新增 `@RestController`、`@RequestMapping` 等路由注解

### 拆分纪律

- 每个新 Service 的职责必须写在类级 Javadoc 中，一句话能讲清
- 单个 Service 文件行数控制在 **300 行以内**
- Service 之间不得循环依赖
- 公共工具方法如果真正被多 Service 共用，可以抽到 `service/plan/support/` 下的 Helper，
  但不得抽到全局 Util 包以伪装行数缩减

### 命名纪律

- 新 Service 命名格式：`Cp<职责名>Service.java`（与现有 `CpPlanService` / `CpDeviationService` 保持一致）
- 测试类命名：`Cp<职责名>ServiceTest.java`
- 私有方法若承担完整业务步骤，必须提取为单独方法（不允许 500 行的巨型方法）

### 测试纪律

- 每次提交前必须运行 `mvn test`（若 maven 不可用，至少要保证每个测试类 `javac` 编译通过）
- 测试不得依赖外部数据库——使用 Mockito mock 掉 Mapper
- 不得使用 `@Ignore` / `@Disabled` 跳过测试来伪造通过

### 事务与日志

- 不得删除 `@Transactional`、`@Retryable` 等关键标注
- 日志级别保持原样，不得调整为 ERROR 或 DEBUG 以改变运行行为
- 新增代码必须保持与原代码一致的异常处理策略（抛 `CpBusinessException`，不裸抛 RuntimeException）

## 文件结构

```
refactor_enterprise/
├── CLAUDE.md                 # 本文件
├── TASK.md                   # 任务定义与验收
├── run.py                    # Agent 执行入口
├── verify.py                 # 静态验收脚本
└── target_project/           # 真实规模 Spring Boot 项目（72 Java 文件 / 7,929 行）
    ├── pom.xml
    └── src/
        ├── main/java/com/example/cp/
        │   ├── CpApplication.java
        │   ├── bo/                # Business Object
        │   ├── config/            # Spring Config
        │   ├── controller/        # REST 层
        │   ├── dto/               # 请求/响应 DTO
        │   ├── enums/             # 枚举
        │   ├── exception/         # 异常体系
        │   ├── mapper/            # MyBatis Mapper
        │   ├── model/             # 领域模型
        │   ├── queue/             # Redis 队列
        │   └── service/           # 服务层（本次重构主战场）
        └── main/resources/application.yml
```

## 补偿面标注

本案例的 CLAUDE.md 规则补偿了模型当前的以下不足：

- 面对大文件时容易"顺便重写一切" → 范围纪律限定改造边界
- 面对企业项目容易忽略事务/日志语义 → 事务与日志纪律兜底
- 容易用巨型 Util 类伪装"已拆分" → 拆分纪律中明确禁止

当模型在企业级代码约束意识上达到更高水平时，CLAUDE.md 可以弱化为建议；
而工具层（Hook、沙箱）仍然承担读写权限与路径白名单等不可让渡的硬约束。
