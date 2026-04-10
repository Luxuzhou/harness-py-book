"""
上下文压缩
==========
生产级四级压缩。对标OpenHarness的compact/ + Hermes的context_compressor。
融入harness_py验证过的: microcompact→snip→compact→reactive。
增加：工具对孤儿修复、迭代摘要更新。
"""

from __future__ import annotations

from typing import Callable

from .token_budget import estimate_tokens


# 可清理的工具结果（对标OpenHarness的compactable tools）
COMPACTABLE_TOOLS = {'read_file', 'bash', 'grep_search', 'glob_search', 'write_file', 'edit_file'}


class Compressor:
    """
    四级压缩器。

    Level 1 - Microcompact: 截断旧工具结果（无LLM调用）
    Level 2 - Snip: 删除中间消息，保留首尾
    Level 3 - Compact: LLM摘要压缩（需要llm_call）
    Level 4 - Reactive: API报错时的紧急压缩
    """

    def __init__(self, preserve_messages: int = 4):
        self.preserve = preserve_messages
        self._last_summary: str = ''

    def total_tokens(self, messages: list[dict]) -> int:
        """估算token数。"""
        return estimate_tokens(messages)

    def compress(
        self,
        messages: list[dict],
        target_tokens: int,
        *,
        llm_call: Callable[[str], str] | None = None,
        reactive: bool = False,
    ) -> list[dict]:
        """
        执行压缩，逐级尝试直到满足目标。

        reactive=True时跳过前两级直接做紧急压缩。
        """
        if reactive:
            result = self._snip(messages)
            if llm_call:
                result = self._compact(result, llm_call)
            return self._fix_orphaned_tool_pairs(result)

        # Level 1: Microcompact
        result = self._microcompact(messages)
        if self.total_tokens(result) <= target_tokens:
            return self._fix_orphaned_tool_pairs(result)

        # Level 2: Snip
        result = self._snip(result)
        if self.total_tokens(result) <= target_tokens:
            return self._fix_orphaned_tool_pairs(result)

        # Level 3: Compact (need LLM)
        if llm_call:
            result = self._compact(result, llm_call)

        return self._fix_orphaned_tool_pairs(result)

    def _microcompact(self, messages: list[dict]) -> list[dict]:
        """Level 1: 截断旧的工具结果。"""
        result = []
        n = len(messages)
        for i, msg in enumerate(messages):
            if i >= n - self.preserve:
                result.append(msg)
                continue

            if msg.get('role') == 'tool':
                content = str(msg.get('content', ''))
                if len(content) > 200:
                    try:
                        data = __import__('json').loads(content)
                        tool_name = data.get('tool', '')
                    except Exception:
                        tool_name = ''

                    if tool_name in COMPACTABLE_TOOLS or len(content) > 500:
                        truncated = dict(msg)
                        truncated['content'] = '[truncated] ' + content[:100] + '...'
                        result.append(truncated)
                        continue

            result.append(msg)
        return result

    def _snip(self, messages: list[dict]) -> list[dict]:
        """Level 2: 删除中间消息，保留系统+首轮+尾部。"""
        if len(messages) <= self.preserve + 2:
            return messages

        head = []
        for m in messages:
            head.append(m)
            if m.get('role') == 'user' and len(head) >= 2:
                break

        tail = messages[-self.preserve:]

        snip_msg = {
            'role': 'user',
            'content': f'[snipped] 中间 {len(messages) - len(head) - len(tail)} 条消息已省略。'
            f' 如有需要请重新读取相关文件。',
        }

        return head + [snip_msg] + tail

    def _compact(self, messages: list[dict], llm_call: Callable[[str], str]) -> list[dict]:
        """Level 3: LLM摘要压缩。使用迭代摘要更新。"""
        head = []
        for m in messages:
            head.append(m)
            if m.get('role') == 'user' and len(head) >= 2:
                break

        tail = messages[-self.preserve:]
        middle = messages[len(head):-self.preserve] if len(messages) > len(head) + self.preserve else []

        if not middle:
            return messages

        middle_text = '\n'.join(
            f"[{m.get('role', '?')}] {str(m.get('content', ''))[:300]}"
            for m in middle
        )

        if self._last_summary:
            prompt = (
                f'以下是之前的对话摘要和新增对话内容。请更新摘要，保留关键信息。\n\n'
                f'## 之前的摘要\n{self._last_summary}\n\n'
                f'## 新增内容\n{middle_text}\n\n'
                f'请生成更新后的结构化摘要，包含：目标、已完成的操作、关键决策、下一步。'
            )
        else:
            prompt = (
                f'请将以下对话内容压缩为结构化摘要：\n\n{middle_text}\n\n'
                f'摘要格式：\n## 目标\n## 已完成操作\n## 关键决策\n## 涉及文件\n## 下一步'
            )

        try:
            summary = llm_call(prompt)
            self._last_summary = summary
        except Exception:
            summary = f'[compact failed] {len(middle)} messages compressed'

        compact_msg = {
            'role': 'user',
            'content': f'<context-compaction>\n{summary}\n</context-compaction>',
        }

        return head + [compact_msg] + tail

    def _fix_orphaned_tool_pairs(self, messages: list[dict]) -> list[dict]:
        """修复孤儿工具对。对标Hermes的工具对修复。"""
        call_ids = set()
        answered_ids = set()
        for msg in messages:
            if msg.get('role') == 'assistant':
                for tc in msg.get('tool_calls', []):
                    tc_id = tc.get('id', '')
                    if tc_id:
                        call_ids.add(tc_id)
            if msg.get('role') == 'tool':
                answered_ids.add(msg.get('tool_call_id', ''))

        filtered = [
            msg for msg in messages
            if not (msg.get('role') == 'tool' and msg.get('tool_call_id', '') not in call_ids)
        ]

        fixed: list[dict] = []
        for msg in filtered:
            fixed.append(msg)
            if msg.get('role') != 'assistant':
                continue
            for tc in msg.get('tool_calls', []):
                tc_id = tc.get('id', '')
                if tc_id and tc_id not in answered_ids:
                    tool_name = tc.get('function', {}).get('name', 'unknown')
                    fixed.append({
                        'role': 'tool',
                        'tool_call_id': tc_id,
                        'content': f'[context compacted - {tool_name} result cleared]',
                    })

        return fixed
