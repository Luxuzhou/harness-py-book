"""邮件发送。"""


def send(to: str, subject: str, body: str) -> bool:
    """发送一封邮件。"""
    # 假装调 SMTP
    print(f"-> {to}: {subject}")
    return True
