"""工具系统单元测试。"""

from pathlib import Path

from harness_py.config import AgentConfig
from harness_py.tools import (
    find_best_bash,
    smart_decode,
    tool_edit_file,
    tool_glob_search,
    tool_grep_search,
    tool_read_file,
    tool_write_file,
)


def _cfg(tmpdir: Path) -> AgentConfig:
    return AgentConfig(cwd=tmpdir)


def test_read_file(workspace_tmp_path: Path):
    (workspace_tmp_path / 'test.py').write_text('line1\nline2\nline3\n', encoding='utf-8')
    ok, content = tool_read_file({'path': 'test.py'}, _cfg(workspace_tmp_path))
    assert ok and 'line1' in content


def test_write_file(workspace_tmp_path: Path):
    ok, _ = tool_write_file({'path': 'sub/new.py', 'content': 'hello'}, _cfg(workspace_tmp_path))
    assert ok and (workspace_tmp_path / 'sub' / 'new.py').exists()


def test_edit_file(workspace_tmp_path: Path):
    (workspace_tmp_path / 'x.py').write_text('return 1', encoding='utf-8')
    ok, _ = tool_edit_file(
        {'path': 'x.py', 'old_string': 'return 1', 'new_string': 'return 42'},
        _cfg(workspace_tmp_path),
    )
    assert ok and 'return 42' in (workspace_tmp_path / 'x.py').read_text(encoding='utf-8')


def test_grep_search(workspace_tmp_path: Path):
    (workspace_tmp_path / 'a.py').write_text('def hello():\n    pass\n', encoding='utf-8')
    ok, content = tool_grep_search({'pattern': r'def \w+', 'path': '.'}, _cfg(workspace_tmp_path))
    assert ok and 'hello' in content


def test_glob_search(workspace_tmp_path: Path):
    for name in ['a.py', 'b.py', 'c.txt']:
        (workspace_tmp_path / name).write_text('', encoding='utf-8')
    ok, content = tool_glob_search({'pattern': '*.py', 'path': '.'}, _cfg(workspace_tmp_path))
    assert ok and 'a.py' in content


def test_glob_search_blocks_parent_escape(workspace_tmp_path: Path):
    ok, content = tool_glob_search({'pattern': '../*.py', 'path': '.'}, _cfg(workspace_tmp_path))
    assert not ok
    assert 'Glob pattern escapes working directory' in content


def test_smart_decode():
    assert smart_decode(b'hello') == 'hello'
    assert smart_decode(b'\xff\xfeh\x00i\x00') == 'hi'
    assert smart_decode(b'') == ''
    assert '\ufffd' in smart_decode(b'\x80\x81')


def test_find_best_bash():
    result = find_best_bash()
    if result:
        assert 'WindowsApps' not in result
