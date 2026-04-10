"""
四级上下文压缩器
================
融入Hermes的迭代摘要 + 动态尾部保护 + 工具对完整性检查。
Ch6记忆层的核心组件。

Level 0: Microcompact - 截断旧tool结果
Level 1: Snipping - 替换旧消息为预览
Level 2: Compaction - LLM迭代摘要（保留上次摘要并追加新进展）
Level 3: Reactive - 保留数减半，紧急恢复
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .token_budget import estimate_tokens


@dataclass
class Compressor:
    """四级上下文压缩器。"""

    preserve_messages: int = 4          # 保留最近N条完整消息
    snip_preview_chars: int = 120       # Snipping预览长度
    microcompact_max_chars: int = 500   # Microcompact截断长度
    _previous_summary: str = ''         # Hermes风格：迭代摘要，跨多次压缩保留

    def total_tokens(self, messages: list[dict]) -> int:
        return sum(estimate_tokens(str(m.get('content', ''))) for m in messages)

    def compress(
        self,
        messages: list[dict],
        target_tokens: int,
        *,
        llm_call: Callable[[str], str] | None = None,
        reactive: bool = False,
    ) -> list[dict]:
        """执行压缩。返回压缩后的消息列表。"""
        preserve = self.preserve_messages
        if reactive:
            preserve = max(preserve // 2, 1)

        for pass_num in range(6):
            current = self.total_tokens(messages)
            if current <= target_tokens:
                break

            # Level 0: Microcompact
            messages = self._microcompact(messages, preserve)
            if self.total_tokens(messages) <= target_tokens:
                break

            # Level 1: Snipping
            messages = self._snip(messages, preserve)
            if self.total_tokens(messages) <= target_tokens:
                break

            # Level 2: Compaction（需要LLM）
            if llm_call:
                messages = self._compact(messages, preserve, llm_call)
                if not reactive:
                    break

        # Hermes风格：压缩后检查工具对完整性
        messages = self._fix_orphaned_tool_pairs(messages)
        return messages

    def _microcompact(self, messages: list[dict], preserve: int) -> list[dict]:
        """Level 0: 截断旧tool结果到max_chars。"""
        cutoff = max(len(messages) - preserve * 2, 1)
        result = []
        for i, msg in enumerate(messages):
            if i < cutoff and msg.get('role') == 'tool' and len(str(msg.get('content', ''))) > self.microcompact_max_chars:
                content = str(msg['content'])[:self.microcompact_max_chars] + '\n... [truncated]'
                result.append({**msg, 'content': content})
            else:
                result.append(msg)
        return result

    def _snip(self, messages: list[dict], preserve: int) -> list[dict]:
        """Level 1: 替换旧消息为预览。每次最多裁剪3条。"""
        cutoff = max(len(messages) - preserve * 2, 1)
        result = list(messages)
        snipped = 0
        for i in range(1, cutoff):  # 跳过system消息
            if snipped >= 3:
                break
            msg = result[i]
            content = str(msg.get('content', ''))
            if msg.get('role') == 'tool' and len(content) > 200:
                preview = content[:self.snip_preview_chars].replace('\n', ' ')
                result[i] = {**msg, 'content': f'[snipped] {preview}...'}
                snipped += 1
            elif msg.get('role') == 'assistant' and len(content) > 600:
                preview = content[:self.snip_preview_chars].replace('\n', ' ')
                result[i] = {**msg, 'content': f'[snipped] {preview}...'}
                snipped += 1
        return result

    def _compact(self, messages: list[dict], preserve: int, llm_call) -> list[dict]:
        """Level 2: LLM迭代摘要。Hermes风格：在上次摘要基础上追加新进展。"""
        prefix = [messages[0]] if messages and messages[0].get('role') == 'system' else []
        prefix_count = len(prefix)
        tail = messages[-preserve * 2:] if preserve > 0 else []
        candidates = messages[prefix_count:len(messages) - len(tail)] if tail else messages[prefix_count:]

        if len(candidates) <= 1:
            return messages

        # 构建摘要内容
        history = '\n'.join(
            f'[{m.get("role", "?")}] {str(m.get("content", ""))[:300]}'
            for m in candidates[:20]
        )

        # Hermes风格：迭代更新，不是从头生成
        if self._previous_summary:
            prompt = (
                f'Previous summary:\n{self._previous_summary}\n\n'
                f'New messages since last summary:\n{history}\n\n'
                f'Update the summary with new progress. Keep format:\n'
                f'Goal | Done | In Progress | Decisions | Files | Next Steps'
            )
        else:
            prompt = (
                f'Summarize this conversation:\n{history}\n\n'
                f'Format: Goal | Done | In Progress | Decisions | Files | Next Steps'
            )

        try:
            summary = llm_call(prompt)
            if summary and len(summary) > 30:
                self._previous_summary = summary
                compact_msg = {
                    'role': 'system',
                    'content': f'<system-reminder>Earlier conversation history was compacted.\n\n{summary}\n</system-reminder>',
                }
                return prefix + [compact_msg] + tail
        except Exception as e:
            print(f'  [COMPACT] 摘要生成失败: {e}')

        # 降级：直接丢弃中间消息
        return prefix + tail

    def _fix_orphaned_tool_pairs(self, messages: list[dict]) -> list[dict]:
        """Hermes风格：压缩后修复孤立的tool_call/result对。"""
        # 收集所有tool_call的id
        call_ids = set()
        result_ids = set()
        for msg in messages:
            if msg.get('role') == 'assistant':
                for tc in msg.get('tool_calls', []):
                    call_ids.add(tc.get('id', ''))
            if msg.get('role') == 'tool':
                result_ids.add(msg.get('tool_call_id', ''))

        # 修复：孤立的result（call被压缩了）→ 移除
        # 修复：孤立的call（result被压缩了）→ 插入stub result
        fixed = []
        for msg in messages:
            if msg.get('role') == 'tool' and msg.get('tool_call_id', '') not in call_ids:
                continue  # 移除孤立result
            fixed.append(msg)

        # 插入stub result for orphaned calls
        final = []
        for msg in fixed:
            final.append(msg)
            if msg.get('role') == 'assistant':
                for tc in msg.get('tool_calls', []):
                    tc_id = tc.get('id', '')
                    if tc_id and tc_id not in result_ids:
                        final.append({
                            'role': 'tool',
                            'tool_call_id': tc_id,
                            'content': '[result was compacted]',
                        })
        return final
