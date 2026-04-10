"""
安全与鉴权中间件
坏味道: 鉴权逻辑形同虚设、API端点不验证调用者身份
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

# 坏味道: 硬编码的用户列表（应从数据库/LDAP读取）
BUILTIN_USERS = {
    "admin": {
        "password": "admin123",  # 坏味道: 明文密码
        "role": "admin",
        "name": "系统管理员",
    },
    "lab_user": {
        "password": "lab2024",
        "role": "user",
        "name": "检验科用户",
    },
    "viewer": {
        "password": "viewer123",
        "role": "viewer",
        "name": "只读用户",
    },
}

# 坏味道: 简易token存储（应用Redis/数据库）
_active_tokens: Dict[str, Dict[str, Any]] = {}

security_scheme = HTTPBearer(auto_error=False)


def create_token(username: str) -> str:
    """
    创建访问令牌
    坏味道: 自制token，未使用JWT
    """
    import hashlib
    token = hashlib.sha256(
        f"{username}:{time.time()}:{settings.SECRET_KEY}".encode()
    ).hexdigest()

    _active_tokens[token] = {
        "username": username,
        "created_at": datetime.now().isoformat(),
        "expires_at": (
            datetime.now() +
            timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        ).isoformat(),
        "role": BUILTIN_USERS.get(username, {}).get("role", "user"),
    }

    print(f"[DEBUG] Token created for {username}: {token[:16]}...")
    logger.info(f"Token创建: user={username}")
    return token


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证令牌
    坏味道: 不检查过期时间
    """
    token_data = _active_tokens.get(token)
    if not token_data:
        return None

    # 坏味道: 注释掉了过期检查
    # expires = datetime.fromisoformat(token_data["expires_at"])
    # if datetime.now() > expires:
    #     del _active_tokens[token]
    #     return None

    return token_data


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[Dict[str, Any]]:
    """
    获取当前用户
    坏味道: 无token时不拒绝请求，而是返回None（匿名访问）
    """
    if credentials is None:
        # 坏味道: 允许匿名访问
        print("[DEBUG] Anonymous access allowed")
        return None

    token = credentials.credentials
    user = verify_token(token)
    if user is None:
        # 坏味道: 仅记录日志，不拒绝
        logger.warning(f"Invalid token: {token[:16]}...")
        return None

    return user


def require_role(required_role: str):
    """
    角色验证装饰器（未实际使用）
    坏味道: 定义了但端点未使用
    """
    async def role_checker(
        user: Optional[Dict[str, Any]] = Depends(get_current_user),
    ):
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未认证",
            )
        if user.get("role") != required_role and user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="权限不足",
            )
        return user

    return role_checker


def login(username: str, password: str) -> Optional[str]:
    """
    用户登录
    坏味道: 明文密码比较
    """
    user = BUILTIN_USERS.get(username)
    if not user:
        logger.warning(f"登录失败: 用户不存在 {username}")
        return None

    # 坏味道: 明文比较密码
    if user["password"] != password:
        logger.warning(f"登录失败: 密码错误 {username}")
        return None

    token = create_token(username)
    logger.info(f"登录成功: {username}")
    return token
