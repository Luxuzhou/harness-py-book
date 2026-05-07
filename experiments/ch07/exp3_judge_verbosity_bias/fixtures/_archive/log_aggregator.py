"""按级别和小时聚合日志。"""
import json                                   # bug: 缺 defaultdict
from typing import Iterable                   # bug: 缺 datetime


def aggregate(log_lines: Iterable[str]) -> dict[str, dict[str, int]]:
    """每行是 JSON：{ts, level, msg}。返回 {level: {hour: count}}。"""
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for line in log_lines:
        rec = json.loads(line)
        ts = datetime.fromisoformat(rec['ts'])
        hour_key = ts.strftime('%Y-%m-%d %H:00')
        out[rec['level']][hour_key] += 1
    return {k: dict(v) for k, v in out.items()}
