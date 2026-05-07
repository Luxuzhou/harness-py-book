"""配置测试。"""

from config import VERSION, get_config

# TODO: 增加环境变量测试
def test_version():
    assert VERSION == "1.0.0"


def test_get_config():
    cfg = get_config()
    assert cfg["version"] == "1.0.0"
