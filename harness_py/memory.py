"""
记忆管理 + Dream整理
=====================
Ch6记忆层。Hermes风格围栏注入 + Claude Code风格Auto Memory + Dream四阶段。
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path


MAX_MEMORY_LINES = 200
MAX_MEMORY_CHARS = 5_000


def get_memory_dir(cwd: Path) -> Path:
    """按项目隔离的memory目录。"""
    try:
        r = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                           capture_output=True, text=True, timeout=5, cwd=str(cwd))
        root = r.stdout.strip() if r.returncode == 0 else str(cwd.resolve())
    except Exception:
        root = str(cwd.resolve())
    key = root.replace('/', '-').replace('\\', '-').replace(':', '-').lstrip('-')
    return Path.home() / '.claude' / 'projects' / key / 'memory'


def load_memory_bundle(cwd: Path) -> str | None:
    """加载MEMORY.md索引（前200行）。用Hermes风格围栏包裹防止prompt injection。"""
    mem_dir = get_memory_dir(cwd)
    index = mem_dir / 'MEMORY.md'
    if not index.exists():
        return None
    text = index.read_text(encoding='utf-8')
    lines = text.splitlines()[:MAX_MEMORY_LINES]
    content = '\n'.join(lines)
    if len(content) > MAX_MEMORY_CHARS:
        content = content[:MAX_MEMORY_CHARS]
    if not content.strip():
        return None
    # Hermes风格围栏：防止模型混淆memory内容和用户指令
    return f'<memory-context>\n{content}\n</memory-context>'


def write_memory(cwd: Path, title: str, content: str, filename: str | None = None) -> Path:
    """写入一条记忆。"""
    mem_dir = get_memory_dir(cwd)
    mem_dir.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = re.sub(r'[^\w\-]', '_', title.lower())[:50] + '.md'
    path = mem_dir / filename
    path.write_text(f'---\nname: {title}\n---\n\n{content}\n', encoding='utf-8')
    # 更新索引
    index = mem_dir / 'MEMORY.md'
    existing = index.read_text(encoding='utf-8') if index.exists() else ''
    line = f'- [{title}]({filename})'
    if line not in existing:
        with open(index, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    return path


def dream(cwd: Path) -> dict:
    """Dream四阶段整理。返回 {merged, removed, date_fixed}。"""
    mem_dir = get_memory_dir(cwd)
    if not mem_dir.exists():
        return {'merged': 0, 'removed': 0, 'date_fixed': 0}

    result = {'merged': 0, 'removed': 0, 'date_fixed': 0}
    today = datetime.now().strftime('%Y-%m-%d')

    for tf in list(mem_dir.glob('*.md')):
        if tf.name == 'MEMORY.md':
            continue
        try:
            text = tf.read_text(encoding='utf-8')
        except OSError:
            continue
        original = text

        # 相对日期→绝对日期
        for rel in ['今天', 'today']:
            if rel in text:
                text = text.replace(rel, today)
                result['date_fixed'] += 1

        # 去重复行
        lines = text.splitlines()
        seen = set()
        deduped = []
        for line in lines:
            norm = line.strip().lower()
            if norm and norm in seen:
                result['merged'] += 1
                continue
            if norm:
                seen.add(norm)
            deduped.append(line)
        text = '\n'.join(deduped)

        # 空文件删除
        content_only = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL).strip()
        if not content_only:
            tf.unlink(missing_ok=True)
            result['removed'] += 1
            continue

        if text != original:
            tf.write_text(text, encoding='utf-8')

    # 重建索引
    entries = []
    for tf in sorted(mem_dir.glob('*.md')):
        if tf.name == 'MEMORY.md':
            continue
        entries.append(f'- [{tf.stem}]({tf.name})')
    (mem_dir / 'MEMORY.md').write_text('\n'.join(entries[:MAX_MEMORY_LINES]) + '\n', encoding='utf-8')

    return result
