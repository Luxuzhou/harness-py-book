# Case 1: 遗留系统重构

## 背景

你面前是一个运行了两年的库存管理系统（Inventory Management System）。
它最初由一个人在一周内快速开发完成，之后只做过零星的修补。

系统能跑，但每次改动都很痛苦。典型的"遗留系统"。

## 当前状态

- `target_project/src/app.py` — 主入口，一个 God Class `InventoryApp` 承载了所有逻辑（~450行）
- `target_project/src/models.py` — 数据模型，但混入了业务逻辑
- `target_project/src/database.py` — SQLite操作，但直接拼SQL字符串
- `target_project/src/utils.py` — 工具函数，职责混乱（格式化+校验+IO全混一起）
- `target_project/tests/test_basic.py` — 只有3个测试，覆盖率不到20%

## 重构目标

### 阶段一：理解（不修改任何代码）
1. 阅读全部源码，绘制依赖关系图
2. 识别并列出所有代码坏味道（至少找出8个）
3. 按重构优先级排序，写出重构计划

### 阶段二：安全网（只加测试，不改业务代码）
4. 为现有功能补充单元测试，覆盖核心路径
5. 确保所有新测试通过
6. 测试覆盖率达到60%以上

### 阶段三：重构（每步改完跑测试）
7. 拆分 God Class：将 `InventoryApp` 拆为 `ProductService`、`OrderService`、`ReportService`
8. 提取数据访问层：将SQL操作封装为 `Repository` 模式
9. 消除硬编码：将配置项提取到 `config.py`
10. 修复 `utils.py` 的职责混乱：拆为 `formatters.py` 和 `validators.py`

### 阶段四：验证
11. 所有原有测试 + 新测试通过
12. 生成重构前后的代码质量对比报告，写入 `refactor_report.md`

## 约束

- 每次修改后必须运行测试
- 不能改变外部行为（纯重构，不加新功能）
- 不能删除任何公开接口（保持向后兼容）
- 重构步骤必须可追溯（每步一个明确的commit message风格的说明）

## 验收标准

- [ ] 测试覆盖率 ≥ 60%
- [ ] God Class `InventoryApp` 被拆为 ≥ 3 个职责单一的类
- [ ] SQL字符串拼接被消除
- [ ] 所有硬编码路径/配置被提取
- [ ] 所有测试通过
- [ ] 生成 `refactor_report.md`
