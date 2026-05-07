"""
模拟 7.4.2 章节描述的场景：pytest 输出夹杂乱码字节。
真实诱因：跨平台 bash 编码不一致（WSL bash 输出 UTF-16 BOM）。
这里通过 conftest 主动写入会触发 GBK 解码失败的字节序列，模拟同样的视觉效果。
"""
import sys


def pytest_configure(config):
    # 在 collection 之前往 stderr 直接写入会被多种解码失败的字节序列。
    # 每次跑 pytest 都会输出相同的乱码（hash 完全一致），触发 LoopGuard 检测 1。
    raw = b'\xff\xfe\xa0\xa1\xfd\xfc\xf0\x9f\x98\xb0' * 8 + b'\n'
    try:
        sys.stderr.buffer.write(raw)
        sys.stderr.buffer.flush()
    except Exception:
        pass
