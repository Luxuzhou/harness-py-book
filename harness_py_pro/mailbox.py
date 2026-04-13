"""
Agent间消息队列
==============
基于文件的异步消息传递，用于多Agent协作中的结构化通信。
比直接共享文件更规范：有消息类型、发送者、时间戳、已读状态。

对标OpenHarness swarm/mailbox.py，但大幅简化：
  - 每个Agent一个jsonl收件箱文件
  - 发送消息 = 往接收者的jsonl文件追加一行
  - 广播 = 往所有已知Agent的收件箱追加
  - 线程安全（文件操作加锁）

消息类型约定：
  task_result         — 任务执行结果
  permission_request  — 权限/确认请求
  feedback            — 人类或Agent反馈
  status              — 状态通知
  artifact            — 产物交付通知

典型用法::

    mb = Mailbox(work_dir / '.mailbox')
    mb.send('architect', 'java_dev', 'task_result', 'plan.md已生成')
    messages = mb.receive('java_dev')
    mb.broadcast('architect', 'status', '架构设计完成，可以开始开发')
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# 消息数据模型
# ---------------------------------------------------------------------------

# 合法消息类型
VALID_MSG_TYPES = frozenset({
    'task_result',
    'permission_request',
    'feedback',
    'status',
    'artifact',
})

BROADCAST_RECEIVER = '*'


@dataclass
class Message:
    """单条Agent间消息。

    Attributes:
        id:        消息唯一ID。
        sender:    发送者Agent名。
        receiver:  接收者Agent名，``'*'`` 表示广播。
        msg_type:  消息类型（见 VALID_MSG_TYPES）。
        content:   消息正文。
        timestamp: 发送时间戳（epoch秒）。
        read:      是否已读。
        metadata:  附加键值对（如文件路径、优先级等）。
    """

    id: str
    sender: str
    receiver: str
    msg_type: str
    content: str
    timestamp: float = 0.0
    read: bool = False
    metadata: dict = field(default_factory=dict)

    # -- 序列化 ---------------------------------------------------------------

    def to_dict(self) -> dict:
        """导出为可JSON序列化的字典。"""
        return {
            'id': self.id,
            'sender': self.sender,
            'receiver': self.receiver,
            'msg_type': self.msg_type,
            'content': self.content,
            'timestamp': self.timestamp,
            'read': self.read,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Message:
        """从字典恢复。"""
        return cls(
            id=d['id'],
            sender=d['sender'],
            receiver=d['receiver'],
            msg_type=d['msg_type'],
            content=d['content'],
            timestamp=d.get('timestamp', 0.0),
            read=d.get('read', False),
            metadata=d.get('metadata', {}),
        )


# ---------------------------------------------------------------------------
# 邮箱
# ---------------------------------------------------------------------------

class Mailbox:
    """Agent邮箱系统。

    每个Agent拥有一个收件箱文件 ``<agent_name>.jsonl``。
    所有消息以JSON Lines格式追加存储，一行一条。
    线程安全：并发读写通过 ``threading.Lock`` 保护。

    Usage::

        mb = Mailbox(work_dir / '.mailbox')
        mb.send('architect', 'java_dev', 'task_result', 'plan.md已生成')
        messages = mb.receive('java_dev')
        mb.send('java_dev', 'qa', 'artifact', 'java_module/编译通过')
        mb.broadcast('architect', 'status', '架构设计完成')
    """

    def __init__(self, mailbox_dir: Path):
        self.mailbox_dir = Path(mailbox_dir)
        self._lock = threading.Lock()
        self.mailbox_dir.mkdir(parents=True, exist_ok=True)

    # -- 发送 -----------------------------------------------------------------

    def send(
        self,
        sender: str,
        receiver: str,
        msg_type: str,
        content: str,
        **metadata,
    ) -> str:
        """发送消息给指定Agent，返回消息ID。

        Args:
            sender:   发送者Agent名。
            receiver: 接收者Agent名。
            msg_type: 消息类型（应为 VALID_MSG_TYPES 之一）。
            content:  消息正文。
            **metadata: 附加键值对。

        Returns:
            消息ID (UUID hex)。

        Raises:
            ValueError: 如果 msg_type 不在合法类型中。
        """
        if msg_type not in VALID_MSG_TYPES:
            raise ValueError(
                f'无效消息类型 {msg_type!r}，合法值: {sorted(VALID_MSG_TYPES)}'
            )

        msg = Message(
            id=uuid4().hex[:12],
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            content=content,
            timestamp=time.time(),
            metadata=metadata,
        )

        self._append(receiver, msg)
        return msg.id

    def broadcast(
        self,
        sender: str,
        msg_type: str,
        content: str,
        **metadata,
    ) -> str:
        """广播消息给所有已知Agent（不含发送者自身）。

        "已知Agent"= mailbox_dir下已有 ``.jsonl`` 文件的Agent。

        Returns:
            消息ID。
        """
        if msg_type not in VALID_MSG_TYPES:
            raise ValueError(
                f'无效消息类型 {msg_type!r}，合法值: {sorted(VALID_MSG_TYPES)}'
            )

        msg = Message(
            id=uuid4().hex[:12],
            sender=sender,
            receiver=BROADCAST_RECEIVER,
            msg_type=msg_type,
            content=content,
            timestamp=time.time(),
            metadata=metadata,
        )

        agents = self._known_agents()
        for agent in agents:
            if agent != sender:
                self._append(agent, msg)

        return msg.id

    # -- 接收 -----------------------------------------------------------------

    def receive(
        self,
        agent_name: str,
        unread_only: bool = True,
    ) -> list[Message]:
        """接收指定Agent的消息。

        Args:
            agent_name: Agent名。
            unread_only: 只返回未读消息（默认True）。

        Returns:
            消息列表，按时间升序。
        """
        messages = self._read_inbox(agent_name)
        if unread_only:
            messages = [m for m in messages if not m.read]
        return messages

    # -- 标记已读 --------------------------------------------------------------

    def mark_read(self, agent_name: str, message_id: str):
        """标记指定Agent收件箱中的某条消息为已读。

        遍历该Agent的所有消息，将匹配ID的消息标记为已读后重写文件。
        """
        messages = self._read_inbox(agent_name)
        changed = False
        for m in messages:
            if m.id == message_id and not m.read:
                m.read = True
                changed = True
                break
        if changed:
            self._rewrite_inbox(agent_name, messages)

    # -- 对话历史 --------------------------------------------------------------

    def get_conversation(
        self,
        agent_a: str,
        agent_b: str,
    ) -> list[Message]:
        """获取两个Agent之间的全部消息（双向），按时间排序。"""
        a_inbox = self._read_inbox(agent_a)
        b_inbox = self._read_inbox(agent_b)

        conv: list[Message] = []
        for m in a_inbox:
            if m.sender == agent_b or (
                m.sender == agent_a and m.receiver == agent_b
            ):
                conv.append(m)
        for m in b_inbox:
            if m.sender == agent_a and m.receiver == agent_b:
                # 避免重复（广播消息可能在两边都有）
                if not any(c.id == m.id for c in conv):
                    conv.append(m)

        conv.sort(key=lambda m: m.timestamp)
        return conv

    # -- 清空 -----------------------------------------------------------------

    def clear(self, agent_name: str):
        """清空指定Agent的收件箱。"""
        inbox_file = self._inbox_path(agent_name)
        with self._lock:
            if inbox_file.exists():
                inbox_file.write_text('', encoding='utf-8')

    # -- 统计 -----------------------------------------------------------------

    def stats(self, agent_name: str) -> dict:
        """返回Agent邮箱统计信息。"""
        messages = self._read_inbox(agent_name)
        unread = sum(1 for m in messages if not m.read)
        by_type: dict[str, int] = {}
        for m in messages:
            by_type[m.msg_type] = by_type.get(m.msg_type, 0) + 1
        return {
            'total': len(messages),
            'unread': unread,
            'by_type': by_type,
        }

    # -- 内部方法 --------------------------------------------------------------

    def _inbox_path(self, agent_name: str) -> Path:
        """Agent收件箱文件路径。"""
        # 规范化名称：小写、去空格
        safe_name = agent_name.strip().lower().replace(' ', '_')
        return self.mailbox_dir / f'{safe_name}.jsonl'

    def _known_agents(self) -> list[str]:
        """返回所有已知Agent名（即有收件箱文件的）。"""
        agents = []
        for p in self.mailbox_dir.glob('*.jsonl'):
            agents.append(p.stem)
        return agents

    def _append(self, receiver: str, msg: Message):
        """追加一条消息到接收者的收件箱文件。"""
        inbox_file = self._inbox_path(receiver)
        line = json.dumps(msg.to_dict(), ensure_ascii=False) + '\n'
        with self._lock:
            with open(inbox_file, 'a', encoding='utf-8') as f:
                f.write(line)

    def _read_inbox(self, agent_name: str) -> list[Message]:
        """读取Agent收件箱的全部消息。"""
        inbox_file = self._inbox_path(agent_name)
        if not inbox_file.exists():
            return []
        messages: list[Message] = []
        with self._lock:
            try:
                text = inbox_file.read_text(encoding='utf-8')
            except OSError:
                return []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                messages.append(Message.from_dict(d))
            except (json.JSONDecodeError, KeyError):
                continue  # 跳过损坏行
        messages.sort(key=lambda m: m.timestamp)
        return messages

    def _rewrite_inbox(self, agent_name: str, messages: list[Message]):
        """重写Agent的收件箱文件（用于mark_read等修改操作）。"""
        inbox_file = self._inbox_path(agent_name)
        lines = [
            json.dumps(m.to_dict(), ensure_ascii=False) + '\n'
            for m in messages
        ]
        with self._lock:
            inbox_file.write_text(''.join(lines), encoding='utf-8')
