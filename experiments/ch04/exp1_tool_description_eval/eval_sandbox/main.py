"""应用入口。"""

import requests
from config import VERSION
from utils import helper_foo

print("debug")  # 调试用


def main():
    print(f"App v{VERSION}")
    helper_foo("hello")


if __name__ == "__main__":
    main()
