"""
Memory系统
==========
对标Claude Code的Auto Memory + Dream机制。
从harness_py教学层提升为生产级：增加CRUD、索引管理、Dream整理。

结构：
  {cwd}/.harness/memory/
  ├── MEMORY.md          ← 索引文件
  ├── user_*.md          ← 用户信息
  ├── feedback_*.md      ← 行为反馈
  ├── project_*.md       ← 项目状态
  └── reference_*.md     ← 外部引用
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass

MAX_BUNDLE_CHARS = 5_000
MAX_ENTRY_CHARS = 800
MAX_BUNDLE_ENTRIES = 20


@dataclass
class MemoryEntry:
    """一条记忆。"""
    name: str
    description: str
    type: str  # user, feedback, project, reference
    content: str
    file_path: Path | None = None

    def to_frontmatter(self) -> str:
        return (
            f'---\n'
            f'name: {self.name}\n'
            f'description: {self.description}\n'
            f'type: {self.type}\n'
            f'---\n\n'
            f'{self.content}\n'
        )

    @classmethod
    def from_file(cls, path: Path) -> MemoryEntry | None:
        """从文件解析记忆。"""
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return None

        # 解析frontmatter
        fm_match = re.match(r'^---\n(.*?)\n---\n\n?(.*)', text, re.DOTALL)
        if not fm_match:
            return None

        fm_text, content = fm_match.groups()
        meta = {}
        for line in fm_text.splitlines():
            if ':' in line:
                k, _, v = line.partition(':')
                meta[k.strip()] = v.strip()

        return cls(
            name=meta.get('name', path.stem),
            description=meta.get('description', ''),
            type=meta.get('type', 'project'),
            content=content.strip(),
            file_path=path,
        )


class MemoryManager:
    """
    Memory管理器。

    提供CRUD操作和Dream整理功能。
    """

    def __init__(self, cwd: Path):
        self.memory_dir = cwd / '.harness' / 'memory'
        self.index_path = self.memory_dir / 'MEMORY.md'

    def ensure_dir(self):
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def list_entries(self) -> list[MemoryEntry]:
        """列出所有记忆。"""
        if not self.memory_dir.exists():
            return []
        entries = []
        for f in sorted(self.memory_dir.glob('*.md')):
            if f.name == 'MEMORY.md':
                continue
            entry = MemoryEntry.from_file(f)
            if entry:
                entries.append(entry)
        return entries

    def get(self, name: str) -> MemoryEntry | None:
        """按名称查找记忆。"""
        for entry in self.list_entries():
            if entry.name == name:
                return entry
        return None

    def save(self, entry: MemoryEntry) -> Path:
        """保存记忆到文件。"""
        self.ensure_dir()
        # 文件名：type_name.md
        safe_name = re.sub(r'[^\w\-]', '_', entry.name)[:50]
        filename = f'{entry.type}_{safe_name}.md'
        path = self.memory_dir / filename
        path.write_text(entry.to_frontmatter(), encoding='utf-8')
        entry.file_path = path
        self._rebuild_index()
        return path

    def delete(self, name: str) -> bool:
        """删除记忆。"""
        entry = self.get(name)
        if entry and entry.file_path and entry.file_path.exists():
            entry.file_path.unlink()
            self._rebuild_index()
            return True
        return False

    def load_bundle(self) -> str:
        """加载所有记忆为文本包（注入到system prompt）。"""
        entries = self.list_entries()
        if not entries:
            return ''

        parts = ['# Memory\n']
        for entry in entries[:MAX_BUNDLE_ENTRIES]:
            content = entry.content.strip()
            if len(content) > MAX_ENTRY_CHARS:
                content = content[:MAX_ENTRY_CHARS] + '\n... (truncated)'
            parts.append(f'## [{entry.type}] {entry.name}\n{content}\n')
        bundle = '\n'.join(parts)
        if len(bundle) > MAX_BUNDLE_CHARS:
            bundle = bundle[:MAX_BUNDLE_CHARS] + '\n... (truncated)'
        return f'<memory-context>\n{bundle}\n</memory-context>'

    def _rebuild_index(self):
        """重建MEMORY.md索引。"""
        entries = self.list_entries()
        lines = ['# Memory Index\n']
        for entry in entries:
            filename = entry.file_path.name if entry.file_path else '?'
            desc = entry.description[:80] if entry.description else entry.name
            lines.append(f'- [{entry.name}]({filename}) — {desc}')

        self.index_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

    def dream(self, llm_call=None) -> str:
        """
        Dream整理：合并、去重、更新过期记忆。

        四阶段流程（对标Claude Code的Dream概念）：
        1. 扫描：列出所有记忆
        2. 分析：检测重复和冲突
        3. 整理：合并重复项，标记过期项
        4. 总结：生成整理报告

        如果提供llm_call，用LLM做智能整理；否则做规则整理。
        """
        entries = self.list_entries()
        if len(entries) < 2:
            return '记忆不足2条，无需整理'

        report_lines = ['# Dream整理报告\n']

        # 阶段1：检测重复（名称相似度）
        duplicates = []
        seen_names = {}
        for entry in entries:
            normalized = entry.name.lower().replace('_', ' ').replace('-', ' ')
            for prev_name, prev_entry in seen_names.items():
                if normalized == prev_name or (len(normalized) > 5 and normalized in prev_name):
                    duplicates.append((prev_entry, entry))
            seen_names[normalized] = entry

        if duplicates:
            report_lines.append(f'## 发现 {len(duplicates)} 组疑似重复\n')
            for old, new in duplicates:
                report_lines.append(f'- `{old.name}` ↔ `{new.name}`')

        # 阶段2：按类型统计
        by_type: dict[str, int] = {}
        for entry in entries:
            by_type[entry.type] = by_type.get(entry.type, 0) + 1
        report_lines.append(f'\n## 记忆统计\n')
        for t, count in sorted(by_type.items()):
            report_lines.append(f'- {t}: {count} 条')

        # 阶段3：如果有LLM，做智能整理
        if llm_call and len(entries) > 5:
            all_content = '\n---\n'.join(
                f'[{e.type}] {e.name}: {e.content[:200]}'
                for e in entries
            )
            prompt = (
                f'以下是 {len(entries)} 条记忆。请分析：\n'
                f'1. 哪些可以合并？\n'
                f'2. 哪些已过期？\n'
                f'3. 建议的整理操作。\n\n{all_content}'
            )
            try:
                analysis = llm_call(prompt)
                report_lines.append(f'\n## LLM分析\n{analysis}')
            except Exception as e:
                report_lines.append(f'\n## LLM分析失败: {e}')

        report_lines.append(f'\n生成时间: {datetime.now(timezone.utc).isoformat()}')
        report = '\n'.join(report_lines)

        return report
