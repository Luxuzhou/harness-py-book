---
name: mixed_types
---

- 使用 FastAPI 框架，数据库用 PostgreSQL
- 所有 API 端点放在 api/routes/ 目录下
- 今天决定把日志从 print 改成 structlog
- 数据库操作必须通过 repositories/ 目录的 Repository 类
- 今天修复了一个 bug：患者 ID 字段从 int 改成了 str
- 昨天和团队讨论了认证方案，决定用 JWT
- 所有数据模型放在 models/ 目录
- 日志使用 structlog，不要用 print 或 logging
- 今天加了 CORS 中间件
- 测试用 pytest，放在 tests/ 目录
