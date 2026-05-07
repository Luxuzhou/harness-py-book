"""请求处理器。"""


logger = logging.getLogger(__name__)


def handle(request: dict) -> dict:
    logger.info("handling %s", request.get("id"))
    return {"status": "ok"}
