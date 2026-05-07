"""
为 ch07/exp3 的 10 个任务批量生成 fixture 项目目录。

每个 fixture 是 fixtures/<task_id>/ 下的最小可用 Python 项目：
  - 包含任务需要修改的 src/<module>.py
  - 对于 rename 任务，还包含若干调用方文件

run.py 会按 task_id 把对应 fixture 整体复制到独立 workdir，让 Agent 操作。

执行方式：python _build_fixtures.py
（实验本身不依赖此脚本，仅在初次搭建 / 重置 fixture 时手动运行）
"""
from __future__ import annotations

from pathlib import Path

FIXTURES = Path(__file__).parent

TASKS: dict[str, dict[str, str]] = {
    'ap001': {
        'src/users.py': (
            '"""用户管理。"""\n\n\n'
            'def get_user(uid: int) -> dict | None:\n'
            '    """从数据库按 ID 查用户。"""\n'
            '    # 这里假装调数据库\n'
            '    return {"id": uid, "name": f"user_{uid}", "deleted": False}\n'
        ),
    },
    'ap002': {
        'src/email_sender.py': (
            '"""邮件发送。"""\n\n\n'
            'def send(to: str, subject: str, body: str) -> bool:\n'
            '    """发送一封邮件。"""\n'
            '    # 假装调 SMTP\n'
            '    print(f"-> {to}: {subject}")\n'
            '    return True\n'
        ),
    },
    'ap003': {
        'src/cache.py': (
            '"""内存缓存。"""\n\n\n'
            'class Cache:\n'
            '    def __init__(self) -> None:\n'
            '        self._store: dict = {}\n\n'
            '    def set(self, key: str, value) -> None:\n'
            '        self._store[key] = value\n\n'
            '    def get(self, key: str):\n'
            '        return self._store[key]  # 当前找不到会 KeyError\n'
        ),
    },
    'cd001': {
        'src/config.py': (
            '"""应用配置常量。"""\n\n'
            'PAGE_SIZE = 20\n'
            'MAX_RESULTS = 1000\n'
            'API_TIMEOUT = 30\n'
        ),
    },
    'cd002': {
        'src/retry.py': (
            '"""重试配置。"""\n\n'
            'MAX_RETRIES = 3\n'
            'BACKOFF_FACTOR = 2.0\n'
            'RETRYABLE_STATUS = [408, 429, 500, 502, 503, 504]\n'
        ),
    },
    'ai001': {
        'src/parser.py': (
            '"""解析器。"""\n\n\n'
            'PATTERN = re.compile(r"\\d+")\n\n\n'
            'def parse(text: str) -> list[str]:\n'
            '    return PATTERN.findall(text)\n'
        ),
    },
    'ai002': {
        'src/handlers.py': (
            '"""请求处理器。"""\n\n\n'
            'logger = logging.getLogger(__name__)\n\n\n'
            'def handle(request: dict) -> dict:\n'
            '    logger.info("handling %s", request.get("id"))\n'
            '    return {"status": "ok"}\n'
        ),
    },
    'rn001': {
        'src/auth.py': (
            '"""认证模块。"""\n\n\n'
            'def check_token(token: str) -> bool:\n'
            '    """校验 token 是否有效。"""\n'
            '    return token.startswith("sk-") and len(token) > 8\n'
        ),
        'src/middleware.py': (
            '"""认证中间件。"""\n'
            'from src.auth import check_token\n\n\n'
            'def auth_middleware(request: dict) -> bool:\n'
            '    return check_token(request.get("token", ""))\n'
        ),
        'src/api.py': (
            '"""API 入口。"""\n'
            'from src.auth import check_token\n\n\n'
            'def authorize(request: dict) -> bool:\n'
            '    if not check_token(request.get("token", "")):\n'
            '        return False\n'
            '    return True\n'
        ),
        'src/cli.py': (
            '"""命令行工具。"""\n'
            'from src.auth import check_token\n\n\n'
            'def login(token: str) -> str:\n'
            '    return "ok" if check_token(token) else "denied"\n'
        ),
    },
    'rn002': {
        'src/db.py': (
            '"""数据库访问层。"""\n\n\n'
            'def query_one(sql: str, params: tuple = ()) -> dict | None:\n'
            '    """执行 SQL 取单行。"""\n'
            '    # 假装查数据库\n'
            '    return None\n'
        ),
        'src/repositories.py': (
            '"""仓储层。"""\n'
            'from src.db import query_one\n\n\n'
            'def get_user(uid: int):\n'
            '    return query_one("SELECT * FROM users WHERE id=%s", (uid,))\n\n\n'
            'def get_order(oid: int):\n'
            '    return query_one("SELECT * FROM orders WHERE id=%s", (oid,))\n'
        ),
        'src/services.py': (
            '"""业务服务层。"""\n'
            'from src.db import query_one\n\n\n'
            'def latest_login(uid: int):\n'
            '    return query_one("SELECT MAX(ts) FROM logins WHERE uid=%s", (uid,))\n'
        ),
    },
    'rn003': {
        'src/user_service.py': (
            '"""用户服务。"""\n\n\n'
            'def list_users(offset: int = 0, limit: int = 20) -> list[dict]:\n'
            '    """分页取用户列表。"""\n'
            '    return [{"id": i} for i in range(offset, offset + limit)]\n'
        ),
        'src/views.py': (
            '"""前端视图。"""\n'
            'from src.user_service import list_users\n\n\n'
            'def users_page(page: int = 0):\n'
            '    return list_users(offset=page * 20, limit=20)\n'
        ),
        'src/admin.py': (
            '"""管理后台。"""\n'
            'from src.user_service import list_users\n\n\n'
            'def admin_user_list():\n'
            '    return list_users(offset=0, limit=100)\n'
        ),
    },
}


def main() -> None:
    for task_id, files in TASKS.items():
        task_dir = FIXTURES / task_id
        task_dir.mkdir(exist_ok=True)
        for rel, content in files.items():
            target = task_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        # 让 src/ 成为合法包
        src_init = task_dir / 'src' / '__init__.py'
        if (task_dir / 'src').exists() and not src_init.exists():
            src_init.write_text('', encoding='utf-8')
    print(f'已生成 {len(TASKS)} 个 fixture 项目到 {FIXTURES}/')


if __name__ == '__main__':
    main()
