"""认证模块。"""


def check_token(token: str) -> bool:
    """校验 token 是否有效。"""
    return token.startswith("sk-") and len(token) > 8
