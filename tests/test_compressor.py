"""压缩器单元测试。"""
from harness_py.compressor import Compressor


def test_microcompact():
    comp = Compressor()
    msgs = [{'role': 'system', 'content': 'sys'}]
    msgs += [{'role': 'tool', 'content': 'x' * 1000} for _ in range(10)]
    msgs += [{'role': 'user', 'content': 'latest'}]
    result = comp._microcompact(msgs, preserve=2)
    assert any('[truncated]' in str(m.get('content', '')) for m in result)


def test_snip():
    comp = Compressor()
    msgs = [{'role': 'system', 'content': 'sys'}]
    msgs += [{'role': 'tool', 'content': 'x' * 1000} for _ in range(10)]
    msgs += [{'role': 'user', 'content': 'latest'}]
    result = comp._snip(msgs, preserve=2)
    assert any('[snipped]' in str(m.get('content', '')) for m in result)


def test_compress_reduces_tokens():
    comp = Compressor()
    msgs = [{'role': 'system', 'content': 'sys'}]
    msgs += [{'role': 'tool', 'content': 'content ' * 200} for _ in range(10)]
    msgs += [{'role': 'user', 'content': 'latest'}]
    before = comp.total_tokens(msgs)
    result = comp.compress(msgs, target_tokens=100)
    after = comp.total_tokens(result)
    assert after < before


def test_fix_orphaned_tool_pairs():
    comp = Compressor()
    msgs = [
        {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'tc1', 'function': {'name': 'bash'}}]},
        # 缺少tc1的tool result → 应该被修复
    ]
    result = comp._fix_orphaned_tool_pairs(msgs)
    assert any(m.get('tool_call_id') == 'tc1' for m in result)


if __name__ == '__main__':
    for name, func in list(globals().items()):
        if name.startswith('test_'):
            try:
                func()
                print(f'  PASS {name}')
            except Exception as e:
                print(f'  FAIL {name}: {e}')
