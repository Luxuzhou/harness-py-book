"""用户校验工具。"""


def validate_user(data: dict) -> list[str]:
    """返回错误信息列表；空列表表示数据合法。

    详细规约见 SPEC.md。
    """
    errors = []
    if not data.get('username'):
        errors.append('username is required')
    return errors
