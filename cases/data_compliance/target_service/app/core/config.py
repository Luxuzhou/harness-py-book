"""
配置管理
坏味道: 部分配置硬编码、敏感信息明文
"""

import os
from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 基础配置
    APP_NAME: str = "PBRTQC Data Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # 数据库配置
    # 坏味道: 明文密码
    DATABASE_HOST: str = "192.168.1.100"
    DATABASE_PORT: int = 9000
    DATABASE_NAME: str = "lab_data"
    DATABASE_USER: str = "admin"
    DATABASE_PASSWORD: str = "admin123"  # 坏味道: 硬编码密码

    # Redis缓存
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""

    # API配置
    API_PREFIX: str = "/api/v1"
    MAX_PAGE_SIZE: int = 1000
    DEFAULT_PAGE_SIZE: int = 20

    # 安全配置
    # 坏味道: 硬编码JWT密钥
    SECRET_KEY: str = "super-secret-key-do-not-use-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ALLOWED_ORIGINS: List[str] = ["*"]  # 坏味道: 允许所有来源

    # 导出配置
    # 坏味道: 硬编码路径
    EXPORT_DIR: str = "C:\\Users\\Administrator\\Desktop\\exports"
    MAX_EXPORT_ROWS: int = 100000
    EXPORT_CLEANUP_DAYS: int = 7

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "C:\\pbrtqc_logs\\service.log"  # 坏味道: 硬编码路径

    # PBRTQC配置
    DEFAULT_WINDOW_SIZE: int = 20
    DEFAULT_MA_METHOD: str = "EWMA"
    DEFAULT_ALPHA: float = 0.2
    DEFAULT_CONTROL_SIGMA: float = 3.0
    MIN_DATA_POINTS: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# 全局配置实例
settings = Settings()
