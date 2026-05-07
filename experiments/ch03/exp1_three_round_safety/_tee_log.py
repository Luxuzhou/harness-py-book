"""Tee stdout/stderr 到 logs/{prefix}_{timestamp}.log。

让 run_bare.py / run_harnessed.py / run_progressive.py 自动留档，
读者不必手动 `> some.log` 重定向。

用法（在脚本开头，os.chdir 之后立刻调用）：
    from _tee_log import setup_tee_log
    log_path = setup_tee_log('bare')
    print(f'[log] 本次运行日志：{log_path}')
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path


class _Tee:
    """把写入同时转发到多个底层流。不拥有这些流，不负责关闭它们。"""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, text: str) -> int:
        n = 0
        for st in self._streams:
            try:
                n = st.write(text)
                st.flush()
            except Exception:
                # 不因一个坏流影响其他流
                continue
        return n

    def flush(self) -> None:
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                continue

    def isatty(self) -> bool:
        # 下游代码（比如带颜色的 print）可能查 isatty
        try:
            return bool(self._streams[0].isatty())
        except Exception:
            return False


def setup_tee_log(prefix: str, log_dir: Path | None = None) -> Path:
    """
    把 sys.stdout / sys.stderr tee 到一个 logs/{prefix}_{ts}.log 文件。

    返回日志文件绝对路径。调用方可以打印这个路径告诉用户。
    多次调用会 tee 到新的文件（时间戳不同），不覆盖已有日志。
    """
    # 用 _tee_log.py 自己的 __file__ 定位 exp 目录，避免依赖 sys.argv[0] / cwd
    # （调用方可能已经 os.chdir 过，sys.argv[0] 会被重复解析）
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = log_dir / f'{prefix}_{ts}.log'

    # buffering=1 = 行缓冲，保证 Ctrl-C 中断时日志不丢
    fh = open(log_path, 'w', encoding='utf-8', buffering=1)

    # 在文件开头打一个 header，便于事后复盘
    fh.write(f'# Tee log\n')
    fh.write(f'# prefix: {prefix}\n')
    fh.write(f'# started: {datetime.datetime.now().isoformat()}\n')
    fh.write(f'# cmd: {" ".join(sys.argv)}\n')
    fh.write('# ' + '-' * 60 + '\n')
    fh.flush()

    sys.stdout = _Tee(sys.__stdout__, fh)
    sys.stderr = _Tee(sys.__stderr__, fh)

    return log_path
