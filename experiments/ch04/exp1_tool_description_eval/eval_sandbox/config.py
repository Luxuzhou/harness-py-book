"""项目配置。"""

VERSION = "1.0.0"
DEBUG = False

# TODO: 支持从环境变量加载
def old_name():
    """旧版入口函数。"""
    return VERSION


def get_config():
    return {"version": VERSION, "debug": DEBUG}
