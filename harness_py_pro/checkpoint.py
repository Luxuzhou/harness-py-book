"""
文件检查点与回滚
================
每次工具修改文件前自动快照，支持按检查点回滚。
对标Claude Code的Esc+Esc/rewind功能。

设计：
- 纯内存存储，无外部依赖
- 每个检查点 = {filepath: content_bytes} 快照
- 支持自动检查点（工具执行前）和手动检查点
- 通过git status或文件mtime判断哪些文件需要快照
"""

from __future__ import annotations

import difflib
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============ 数据结构 ============

@dataclass
class Checkpoint:
    """一个检查点快照。"""
    checkpoint_id: str
    label: str
    timestamp: float
    files: dict[str, bytes]     # {相对路径: 文件内容}
    cwd: str


# ============ 工具函数 ============

def _generate_id(label: str, ts: float) -> str:
    """生成检查点ID（短哈希）。"""
    raw = f'{label}:{ts}'.encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def _list_tracked_files(cwd: Path, max_files: int = 500) -> list[Path]:
    """
    列出cwd下需要跟踪的文件。

    策略：优先用git ls-files，失败则扫描目录（跳过隐藏目录和常见忽略目录）。
    """
    import subprocess

    # 尝试git ls-files
    try:
        result = subprocess.run(
            ['git', 'ls-files', '--modified', '--others', '--exclude-standard'],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = []
            for line in result.stdout.strip().splitlines():
                p = cwd / line.strip()
                if p.is_file():
                    paths.append(p)
            if paths:
                return paths[:max_files]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 也尝试git diff获取已修改的tracked文件
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = []
            for line in result.stdout.strip().splitlines():
                p = cwd / line.strip()
                if p.is_file():
                    paths.append(p)
            if paths:
                return paths[:max_files]
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # 回退：扫描目录
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.tox'}
    paths = []
    try:
        for item in cwd.rglob('*'):
            if any(part in skip_dirs for part in item.parts):
                continue
            if item.is_file() and item.suffix in (
                '.py', '.js', '.ts', '.json', '.yaml', '.yml',
                '.toml', '.md', '.txt', '.html', '.css',
            ):
                paths.append(item)
                if len(paths) >= max_files:
                    break
    except OSError:
        pass

    return paths


def _snapshot_files(cwd: Path, file_paths: list[Path]) -> dict[str, bytes]:
    """读取文件内容，返回 {相对路径: 内容bytes}。"""
    snapshot: dict[str, bytes] = {}
    for fp in file_paths:
        try:
            rel = fp.relative_to(cwd)
            snapshot[str(rel)] = fp.read_bytes()
        except (OSError, ValueError):
            continue
    return snapshot


# ============ FileCheckpoint ============

class FileCheckpoint:
    """
    文件检查点管理器。

    用法::

        cp = FileCheckpoint(cwd)
        cid = cp.create()              # 创建检查点（快照当前所有tracked文件）
        # ... Agent修改文件 ...
        cp.rewind(cid)                 # 回滚到检查点
        cp.list_checkpoints()          # 列出所有检查点
        cp.diff(cid)                   # 查看检查点到当前的差异

    实现细节：
    - 内存存储，轻量快速
    - 只快照被修改/新增的文件
    - 支持保留最近N个检查点的清理策略
    """

    def __init__(self, cwd: Path, max_checkpoints: int = 50):
        self.cwd = cwd.resolve()
        self.max_checkpoints = max_checkpoints
        self._checkpoints: list[Checkpoint] = []

    def create(self, label: str = '') -> str:
        """
        创建检查点，返回checkpoint_id。

        Args:
            label: 可选的检查点标签（如 'before-edit-main.py'）

        Returns:
            12字符的检查点ID
        """
        ts = time.time()
        cid = _generate_id(label or 'auto', ts)

        # 获取需要快照的文件
        tracked = _list_tracked_files(self.cwd)
        files = _snapshot_files(self.cwd, tracked)

        cp = Checkpoint(
            checkpoint_id=cid,
            label=label,
            timestamp=ts,
            files=files,
            cwd=str(self.cwd),
        )
        self._checkpoints.append(cp)

        # 自动清理
        if len(self._checkpoints) > self.max_checkpoints:
            self.cleanup(keep_last=self.max_checkpoints)

        return cid

    def rewind(self, checkpoint_id: str) -> list[str]:
        """
        回滚到指定检查点，返回被恢复的文件列表。

        Args:
            checkpoint_id: 目标检查点ID

        Returns:
            被恢复的文件相对路径列表

        Raises:
            ValueError: 检查点不存在
        """
        cp = self._find_checkpoint(checkpoint_id)
        if cp is None:
            raise ValueError(f'Checkpoint not found: {checkpoint_id}')

        restored: list[str] = []
        for rel_path, content in cp.files.items():
            full_path = self.cwd / rel_path
            try:
                # 确保父目录存在
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_bytes(content)
                restored.append(rel_path)
            except OSError:
                continue

        return restored

    def diff(self, checkpoint_id: str) -> dict[str, str]:
        """
        返回检查点到当前的文件差异。

        Args:
            checkpoint_id: 目标检查点ID

        Returns:
            {相对路径: unified_diff文本} 字典，只包含有差异的文件

        Raises:
            ValueError: 检查点不存在
        """
        cp = self._find_checkpoint(checkpoint_id)
        if cp is None:
            raise ValueError(f'Checkpoint not found: {checkpoint_id}')

        diffs: dict[str, str] = {}
        for rel_path, old_content in cp.files.items():
            full_path = self.cwd / rel_path
            try:
                new_content = full_path.read_bytes()
            except OSError:
                # 文件被删除
                new_content = b''

            if old_content == new_content:
                continue

            # 生成unified diff
            try:
                old_lines = old_content.decode('utf-8', errors='replace').splitlines(keepends=True)
                new_lines = new_content.decode('utf-8', errors='replace').splitlines(keepends=True)
                diff_text = ''.join(difflib.unified_diff(
                    old_lines, new_lines,
                    fromfile=f'a/{rel_path}',
                    tofile=f'b/{rel_path}',
                ))
                if diff_text:
                    diffs[rel_path] = diff_text
            except Exception:
                diffs[rel_path] = f'[binary diff: {len(old_content)} -> {len(new_content)} bytes]'

        return diffs

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """
        列出所有检查点的元数据（不含文件内容）。

        Returns:
            检查点信息列表，按时间倒序
        """
        result = []
        for cp in reversed(self._checkpoints):
            result.append({
                'id': cp.checkpoint_id,
                'label': cp.label,
                'timestamp': cp.timestamp,
                'file_count': len(cp.files),
                'total_bytes': sum(len(v) for v in cp.files.values()),
            })
        return result

    def cleanup(self, keep_last: int = 10) -> int:
        """
        清理旧检查点，只保留最近的N个。

        Args:
            keep_last: 保留的检查点数量

        Returns:
            被清理的检查点数量
        """
        if len(self._checkpoints) <= keep_last:
            return 0
        removed = len(self._checkpoints) - keep_last
        self._checkpoints = self._checkpoints[-keep_last:]
        return removed

    def _find_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        """按ID查找检查点。"""
        for cp in self._checkpoints:
            if cp.checkpoint_id == checkpoint_id:
                return cp
        return None

    @property
    def count(self) -> int:
        """当前检查点数量。"""
        return len(self._checkpoints)
