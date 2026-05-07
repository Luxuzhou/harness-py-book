"""解析器。"""


PATTERN = re.compile(r"\d+")


def parse(text: str) -> list[str]:
    return PATTERN.findall(text)
