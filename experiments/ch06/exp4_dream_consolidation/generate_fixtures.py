"""生成 exp4 的 10 份样例 Memory 文件。"""
from __future__ import annotations

from pathlib import Path

FIX = Path(__file__).parent / 'fixtures'
FIX.mkdir(parents=True, exist_ok=True)


MEMORY_FILES = {
    'simple_project.md': """---
name: simple_project
---

- 使用 FastAPI 框架
- 数据库用 PostgreSQL
- 测试用 pytest
""",

    'duplicate_heavy.md': """---
name: duplicate_heavy
---

- 使用 FastAPI 框架，数据库用 PostgreSQL
- 所有 API 端点放在 api/routes/ 目录下
- 测试用 pytest，放在 tests/ 目录
- 使用 FastAPI 框架
- API 端点放在 api/routes/ 目录下
- 所有数据模型放在 models/ 目录
- 日志使用 structlog，不要用 print 或 logging
- 使用 FastAPI 框架
- 测试用 pytest
- API 端点放在 api/routes/ 目录下
""",

    'relative_dates.md': """---
name: relative_dates
---

- 今天决定把日志从 print 改成 structlog
- 今天修复了一个 bug：患者 ID 字段从 int 改成 str
- 今天加了 CORS 中间件
- 昨天和团队讨论了认证方案，决定用 JWT
- 今天部署到 staging 环境
- today: fixed the payment webhook signature validation
""",

    'mixed_types.md': """---
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
""",

    'long_stream.md': """---
name: long_stream
---
""" + '\n'.join(f'- 事件 {i}: 处理了工单 #{1000 + i}' for i in range(250)),

    'empty_after_dedup.md': """---
name: empty_after_dedup
---

- 使用 Python 3.10
- 使用 python 3.10
- Using Python 3.10
""",

    'yaml_front_matter.md': """---
name: yaml_front_matter
description: 带完整元数据的记忆
tags: [infra, config]
created: 2026-03-01
---

- 所有服务都部署在 Kubernetes
- 使用 helm chart 管理配置
- 日志走 Fluent Bit 到 Elasticsearch
""",

    'multilingual.md': """---
name: multilingual
---

- Use FastAPI framework
- 使用 FastAPI 框架
- Deploy to production via helm
- 用 helm 部署到生产
- Tests are in tests/ directory
- 测试代码在 tests/ 目录下
""",

    'chronology.md': """---
name: chronology
---

- 今天修复了 OAuth 回调 bug
- 三天前升级了 Django 到 5.0
- 昨天重构了用户模型
- 上周部署了新的搜索服务
- 今天优化了数据库索引
""",

    'operations_log.md': """---
name: operations_log
---

- 2026-03-15 重启了 cache 集群
- 2026-03-16 部署 v2.3.1 到 staging
- 2026-03-17 回滚 v2.3.1（有 OOM 问题）
- 2026-03-18 部署 v2.3.2，修复 OOM
- 2026-03-18 部署 v2.3.2，修复 OOM
- 2026-03-20 重启了 cache 集群
""",
}


def main():
    for name, content in MEMORY_FILES.items():
        path = FIX / name
        path.write_text(content, encoding='utf-8')
        print(f'wrote {path.name}')


if __name__ == '__main__':
    main()
