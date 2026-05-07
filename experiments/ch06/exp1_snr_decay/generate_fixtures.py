"""
一次性生成 exp1 需要的 20 个 fixture 模块。运行一次即可，产物在 fixtures/modules/ 下。

设计原则：
  - 每个模块 ~80-150 行，包含 imports / 类 / 方法 / docstring
  - 模块之间有真实的依赖关系（auth_service 依赖 user_repository、audit_logger 等），
    便于在 probe 问题中检验 Agent 是否正确识别关系
  - 命名与业务语义一致（auth_service 而非 module_1），接近真实项目
"""
from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent / 'fixtures' / 'modules'
FIXTURES.mkdir(parents=True, exist_ok=True)


def module(name: str, deps: list[str], classes: list[tuple[str, list[str]]], docstring: str) -> str:
    """生成一个模块的源码字符串。"""
    header = f'"""{docstring}"""\n'
    imports = ['from __future__ import annotations', 'import logging', 'import time']
    for d in deps:
        imports.append(f'from . import {d}')
    imports_str = '\n'.join(imports) + '\n\n'
    log_line = f'log = logging.getLogger("{name}")\n\n'

    body_parts = []
    for cls_name, methods in classes:
        body = [f'class {cls_name}:', f'    """{cls_name} 的业务类。"""', '']
        body.append('    def __init__(self, config: dict | None = None):')
        body.append('        self.config = config or {}')
        body.append('        self.started_at = time.time()')
        body.append('')
        for method in methods:
            body.append(f'    def {method}(self, *args, **kwargs):')
            body.append(f'        """{method} 的实现。"""')
            body.append(f'        log.info("{cls_name}.{method} called")')
            body.append('        # TODO: 实现细节')
            body.append('        return True')
            body.append('')
        body_parts.append('\n'.join(body))

    return header + imports_str + log_line + '\n\n'.join(body_parts)


MODULES = [
    # (name, deps, classes, docstring)
    ('auth_service', ['user_repository', 'audit_logger', 'session_store'],
     [('AuthService', ['login', 'logout', 'verify_token', 'refresh_session'])],
     'auth_service: 认证服务，依赖 user_repository/audit_logger/session_store。'),
    ('user_repository', [],
     [('UserRepository', ['find_by_id', 'find_by_email', 'create', 'update', 'delete'])],
     'user_repository: 用户数据访问层，无外部依赖。'),
    ('email_sender', ['template_engine', 'config_loader'],
     [('EmailSender', ['send', 'send_batch', 'retry_failed'])],
     'email_sender: 邮件发送器，依赖 template_engine 和 config_loader。'),
    ('audit_logger', ['config_loader'],
     [('AuditLogger', ['log_event', 'log_access', 'log_error', 'flush'])],
     'audit_logger: 审计日志记录器。所有需要审计的模块都会调用它。'),
    ('rate_limiter', ['cache_client'],
     [('RateLimiter', ['check', 'consume', 'reset'])],
     'rate_limiter: 基于滑动窗口的限流器，使用 cache_client 作为存储后端。'),
    ('cache_client', ['config_loader'],
     [('CacheClient', ['get', 'set', 'delete', 'expire'])],
     'cache_client: Redis 风格的缓存客户端。'),
    ('config_loader', [],
     [('ConfigLoader', ['load', 'reload', 'get_section'])],
     'config_loader: 配置加载器，无外部依赖。'),
    ('job_queue', ['cache_client', 'audit_logger'],
     [('JobQueue', ['enqueue', 'dequeue', 'retry', 'dead_letter'])],
     'job_queue: 后台任务队列，依赖 cache_client 和 audit_logger。'),
    ('metrics_reporter', ['config_loader'],
     [('MetricsReporter', ['incr', 'gauge', 'histogram', 'flush'])],
     'metrics_reporter: 指标上报，用于监控和可观测性。'),
    ('health_checker', ['cache_client', 'user_repository'],
     [('HealthChecker', ['check_cache', 'check_db', 'overall_status'])],
     'health_checker: 健康检查，轮询下游依赖。'),
    ('session_store', ['cache_client'],
     [('SessionStore', ['create_session', 'get_session', 'destroy_session'])],
     'session_store: 会话存储，基于 cache_client。被 auth_service 使用。'),
    ('billing_calculator', ['user_repository', 'audit_logger'],
     [('BillingCalculator', ['calculate_invoice', 'apply_coupon', 'finalize'])],
     'billing_calculator: 账单计算，依赖 user_repository 和 audit_logger。'),
    ('pdf_renderer', ['template_engine'],
     [('PdfRenderer', ['render', 'render_with_header', 'save'])],
     'pdf_renderer: PDF 生成器，使用 template_engine。'),
    ('feature_flags', ['config_loader', 'cache_client'],
     [('FeatureFlags', ['is_enabled', 'variant', 'track_exposure'])],
     'feature_flags: 特性开关系统，读取 config_loader 和 cache_client。'),
    ('webhook_dispatcher', ['job_queue', 'audit_logger'],
     [('WebhookDispatcher', ['dispatch', 'retry', 'dead_letter_handler'])],
     'webhook_dispatcher: Webhook 派发器，使用 job_queue 异步化。'),
    ('scheduler', ['job_queue', 'config_loader'],
     [('Scheduler', ['schedule', 'cancel', 'run_once'])],
     'scheduler: Cron 风格调度器，依赖 job_queue。'),
    ('template_engine', ['config_loader'],
     [('TemplateEngine', ['render', 'compile', 'register_filter'])],
     'template_engine: 模板引擎，读取 config_loader 的模板目录配置。'),
    ('data_validator', [],
     [('DataValidator', ['validate_schema', 'coerce', 'explain_error'])],
     'data_validator: 数据校验器，无外部依赖。'),
    ('csv_exporter', ['data_validator'],
     [('CsvExporter', ['export', 'export_streamed'])],
     'csv_exporter: CSV 导出，依赖 data_validator 做字段校验。'),
    ('search_indexer', ['job_queue', 'user_repository'],
     [('SearchIndexer', ['index', 'delete', 'rebuild'])],
     'search_indexer: 搜索索引器，使用 job_queue 做异步索引任务。'),
]


def main():
    for name, deps, classes, doc in MODULES:
        src = module(name, deps, classes, doc)
        path = FIXTURES / f'{name}.py'
        path.write_text(src, encoding='utf-8')
        print(f'wrote {path.relative_to(FIXTURES.parent.parent)}')
    print(f'\n共生成 {len(MODULES)} 个模块。')


if __name__ == '__main__':
    main()
