"""
配置模块 - 集中管理所有配置项
"""

import os
from pathlib import Path

# 基础配置
class Config:
    """应用配置"""
    
    # 应用信息
    APP_NAME = '库存管理系统 v1.0'
    
    # 业务规则
    LOW_STOCK_THRESHOLD = 10
    MAX_ORDER_ITEMS = 50
    
    # 数据库配置
    DB_PATH = os.environ.get('INVENTORY_DB', 'inventory.db')
    
    # 路径配置
    BASE_DIR = Path.cwd()
    DATA_DIR = BASE_DIR / 'data'
    REPORT_DIR = BASE_DIR / 'reports'
    EXPORT_DIR = BASE_DIR / 'exports'
    BACKUP_DIR = BASE_DIR / 'backup'
    LOG_DIR = BASE_DIR / 'logs'
    
    # 日志配置
    LOG_FILE = LOG_DIR / 'inventory.log'
    
    # 验证配置
    BANNED_PRODUCT_NAMES = ['测试', 'test', 'xxx', 'null', 'undefined']
    MAX_PRODUCT_NAME_LENGTH = 100
    
    # 订单状态映射
    ORDER_STATUS_MAPPING = {
        'pending': '待处理',
        'confirmed': '已确认',
        'shipped': '已发货',
        'completed': '已完成',
        'cancelled': '已取消',
    }
    
    @classmethod
    def init_dirs(cls):
        """初始化必要的目录"""
        dirs = [cls.DATA_DIR, cls.REPORT_DIR, cls.EXPORT_DIR, 
                cls.BACKUP_DIR, cls.LOG_DIR]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)


# 开发环境配置
class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    DB_PATH = 'inventory_dev.db'


# 测试环境配置
class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DB_PATH = ':memory:'  # 内存数据库


# 生产环境配置
class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    # 生产环境使用环境变量或固定路径
    DB_PATH = os.environ.get('INVENTORY_DB', '/var/lib/inventory/inventory.db')
    REPORT_DIR = Path('/var/reports/inventory')
    EXPORT_DIR = Path('/var/exports/inventory')
    LOG_DIR = Path('/var/log/inventory')


# 根据环境选择配置
def get_config(env=None):
    """获取配置实例"""
    if env is None:
        env = os.environ.get('INVENTORY_ENV', 'development')
    
    config_map = {
        'development': DevelopmentConfig,
        'testing': TestingConfig,
        'production': ProductionConfig,
    }
    
    config_class = config_map.get(env.lower(), DevelopmentConfig)
    return config_class()