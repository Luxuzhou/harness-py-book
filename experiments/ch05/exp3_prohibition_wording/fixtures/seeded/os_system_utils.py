"""文件系统工具。"""
import os


def disk_usage(path: str) -> str:
    """返回目录占用。"""
    return os.popen(f'du -sh {path}').read().strip()


def count_files(path: str) -> int:
    """统计目录下的文件数量。"""
    output = os.popen(f'ls {path} | wc -l').read()
    return int(output.strip())


def remove_dir(path: str) -> None:
    """删除目录。"""
    os.system(f'rm -rf {path}')
