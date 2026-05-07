"""写入模块。"""

import json


class Writer:
    def __init__(self, path: str):
        self.path = path

    def write(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f)
