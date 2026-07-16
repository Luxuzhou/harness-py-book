# 遗留系统重构任务定义

## 任务背景

`target_project/` 是一个参照真实临床路径管理系统脱敏改写的 Spring Boot 企业级 Java 项目。
当前读者基线包含 92 个 Java 生产源文件、约 10,127 行生产代码，以及 7 个计划服务相关测试类。
其中 `CpPlanService.java` 已经膨胀到 **1,266 行**，承担了从计划生命周期管理、路径依从率计算、
变更审计、批量操作到缓存清理的多项职责，是典型的 **God Class**。

Agent 的任务是把 `CpPlanService` 按业务职责拆解为独立的服务，**不破坏对外 REST 接口**，
**不引入新功能**，并确保编译通过、对外行为不变。

---

## 核心验收项

### 验收项 1：God Class 拆分

- `CpPlanService.java` 的代码行数必须小于 **400 行**
- `service/plan/` 下必须形成至少 **5 个** 职责单一的专职 `*Service.java` 文件，分别承担：
  - 计划 CRUD 生命周期管理
  - 路径依从率计算
  - 批量操作
  - 变更审计
  - 缓存管理或 DTO/BO 组装

### 验收项 2：对外契约不变

Controller 类级前缀 `@RequestMapping("/api/cp/plan")` 必须保持不变。
以下接口路径、HTTP 方法、请求/响应 DTO 字段必须完全保持不变：

- `POST /api/cp/plan/create`
- `PUT  /api/cp/plan/update/{planId}`
- `DELETE /api/cp/plan/delete/{planId}`
- `GET  /api/cp/plan/detail/{planId}`
- `GET  /api/cp/plan/page`
- `GET  /api/cp/plan/list`
- `POST /api/cp/plan/apply`
- `POST /api/cp/plan/batch/status`
- `POST /api/cp/plan/batch/calc`
- `GET  /api/cp/plan/changes/{planId}`
- `GET  /api/cp/plan/stats/count`

### 验收项 3：依赖倒置

- `CpPlanController` 不得直接调用 `CpPlanService`
- 必须通过各个 **专职 Service** 完成具体工作
- `CpPlanService` 如果保留，只能承担编排职责

### 验收项 4：单元测试

每个承接核心职责的 `*Service.java` 必须有对应的 `*ServiceTest.java`：
- 使用 JUnit 5
- 每个测试类至少 3 个测试方法
- 覆盖正常路径 + 至少 1 个异常路径

### 验收项 5：编译通过

`mvn compile` 或 `javac` 在 `target_project/` 下必须通过，不允许 error。

### 验收项 6：变更范围限制

- 不得新增业务 endpoint
- 不得修改 `CpHospitalInfo`、`CpPathwayPlan` 等领域模型字段
- 不得删除现有的 `@Transactional` 标注
- 不得关闭日志、异常处理链路

---

## 禁止项

- 不得把业务逻辑改用 Kotlin、Scala 或任意非 Java 语言
- 不得引入新的第三方依赖（pom.xml 冻结）
- 不得合并原本独立的 Service 到 Controller 里
- 不得为了缩小 `CpPlanService` 而把逻辑挪到 Util 静态方法里（那只是伪装的 God Class）

---

## 运行入口

```bash
python cases/refactor_enterprise/run.py     # Agent 执行重构
python cases/refactor_enterprise/verify.py  # 静态验收
```

---

## 完成后的产出

1. `CpPlanService.java` 瘦身到 < 400 行
2. `service/plan/` 目录下形成 5+ 个职责清晰的专职 Service 文件
3. `src/test/java/com/example/cp/service/plan/` 下对应测试覆盖保持通过
4. `REFACTOR_REPORT.md`：改造前后的 LOC 对比、依赖关系图、关键决策
