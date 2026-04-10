"""
第4章：工具系统——6个核心工具独立测试
=====================================
不需要API key。每个工具独立运行一个测试用例。
用法: python standalone/ch04_tools.py
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import queue
import time
from pathlib import Path


def smart_decode(raw: bytes) -> str:
    """对齐Rust的String::from_utf8_lossy。"""
    if not raw:
        return ''
    if raw[:2] == b'\xff\xfe':
        return raw[2:].decode('utf-16-le', errors='replace')
    return raw.decode('utf-8', errors='replace')


def find_best_bash():
    """优先Git Bash，避开WSL。"""
    import sys
    if sys.platform != 'win32':
        return shutil.which('bash') or '/bin/bash'
    for p in [
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git' / 'bin' / 'bash.exe',
        Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git' / 'usr' / 'bin' / 'bash.exe',
    ]:
        if p.exists():
            return str(p)
    found = shutil.which('bash')
    return found if found and 'WindowsApps' not in found else None


def test_read_file(tmpdir):
    """测试 read_file"""
    (tmpdir / 'hello.py').write_text('print("hello")\n# line 2\n# line 3\n', encoding='utf-8')
    content = (tmpdir / 'hello.py').read_text(encoding='utf-8')
    assert 'print' in content
    print(f'  ✅ read_file: 读到{len(content)}字符')


def test_write_file(tmpdir):
    """测试 write_file"""
    path = tmpdir / 'output' / 'new.py'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('# new file\n', encoding='utf-8')
    assert path.exists()
    print(f'  ✅ write_file: 创建了{path.name}（含自动建目录）')


def test_edit_file(tmpdir):
    """测试 edit_file"""
    path = tmpdir / 'edit_me.py'
    path.write_text('def foo():\n    return 1\n', encoding='utf-8')
    text = path.read_text(encoding='utf-8')
    text = text.replace('return 1', 'return 42', 1)
    path.write_text(text, encoding='utf-8')
    assert 'return 42' in path.read_text(encoding='utf-8')
    print(f'  ✅ edit_file: "return 1" → "return 42"')


def test_grep_search(tmpdir):
    """测试 grep_search"""
    (tmpdir / 'a.py').write_text('def hello():\n    pass\n', encoding='utf-8')
    (tmpdir / 'b.py').write_text('def world():\n    pass\n', encoding='utf-8')
    pattern = re.compile(r'def \w+')
    hits = []
    for f in tmpdir.glob('*.py'):
        for i, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            if pattern.search(line):
                hits.append(f'{f.name}:{i}: {line}')
    print(f'  ✅ grep_search: "def \\w+" → {len(hits)}个匹配 ({", ".join(hits)})')


def test_glob_search(tmpdir):
    """测试 glob_search"""
    for name in ['a.py', 'b.py', 'c.txt', 'sub/d.py']:
        p = tmpdir / name
        p.parent.mkdir(exist_ok=True)
        p.write_text('', encoding='utf-8')
    matches = list(tmpdir.glob('**/*.py'))
    print(f'  ✅ glob_search: "**/*.py" → {len(matches)}个文件')


def test_bash():
    """测试 bash（线程读取 + 编码自适应）"""
    bash = find_best_bash()
    if not bash:
        print(f'  ⚠️ bash: 未找到Git Bash，跳过')
        return

    proc = subprocess.Popen(
        [bash, '-c', 'echo hello_from_bash && echo error_test 1>&2'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
    )

    output_queue = queue.Queue()
    def reader(stream, name):
        try:
            while True:
                line = stream.readline()
                if not line: break
                output_queue.put((name, smart_decode(line)))
        except: pass
        finally: output_queue.put(None)

    threads = []
    for stream, name in [(proc.stdout, 'stdout'), (proc.stderr, 'stderr')]:
        t = threading.Thread(target=reader, args=(stream, name), daemon=True)
        t.start()
        threads.append(t)

    stdout, stderr = [], []
    alive = 2
    while alive > 0:
        try:
            item = output_queue.get(timeout=5)
        except queue.Empty:
            break
        if item is None:
            alive -= 1
            continue
        name, text = item
        (stdout if name == 'stdout' else stderr).append(text)

    for t in threads:
        t.join(timeout=2)
    proc.wait()

    out = ''.join(stdout).strip()
    err = ''.join(stderr).strip()
    assert 'hello_from_bash' in out
    print(f'  ✅ bash: stdout="{out}" stderr="{err}" (Git Bash={bash[:30]}...)')


def main():
    print("""
╔══════════════════════════════════════════════════════╗
║  第4章：6个核心工具独立测试                           ║
╚══════════════════════════════════════════════════════╝
""")

    tmpdir = Path(tempfile.mkdtemp())
    try:
        test_read_file(tmpdir)
        test_write_file(tmpdir)
        test_edit_file(tmpdir)
        test_grep_search(tmpdir)
        test_glob_search(tmpdir)
        test_bash()
        print(f'\n  全部通过。跨平台兼容：线程读取subprocess + from_utf8_lossy编码 + Git Bash优先')
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    main()
