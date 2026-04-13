"""
Git操作封装
===========
提供检查点、worktree隔离、安全的git命令执行。
对标OpenHarness的worktree.py(316行)和Claude Code的EnterWorktree/ExitWorktree。

设计：
- 所有git命令通过 git_command() 统一执行，自带超时和错误处理
- WorktreeManager为多Agent场景提供隔离的工作目录
- 纯标准库，只依赖subprocess
"""

from __future__ import annotations

import subprocess
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============ 安全执行 ============

def git_command(
    *args: str,
    cwd: Path | str | None = None,
    timeout: int = 10,
) -> str | None:
    """
    安全执行git命令，返回stdout或None。

    Args:
        *args: git子命令和参数，如 'status', '--short'
        cwd: 工作目录
        timeout: 超时秒数

    Returns:
        命令stdout文本，失败返回None
    """
    cmd = ['git'] + list(args)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


# ============ 查询函数 ============

def is_git_repo(cwd: Path) -> bool:
    """
    检查目录是否是git仓库（或在git仓库内部）。

    Args:
        cwd: 要检查的目录

    Returns:
        是否在git仓库中
    """
    result = git_command('rev-parse', '--is-inside-work-tree', cwd=cwd)
    return result == 'true'


def repo_root(cwd: Path) -> Path | None:
    """
    获取git仓库根目录。

    Args:
        cwd: 当前目录

    Returns:
        仓库根目录Path，非git仓库返回None
    """
    result = git_command('rev-parse', '--show-toplevel', cwd=cwd)
    if result:
        return Path(result)
    return None


def current_branch(cwd: Path) -> str:
    """
    获取当前分支名。

    Args:
        cwd: 工作目录

    Returns:
        分支名，获取失败返回 'HEAD'
    """
    result = git_command('rev-parse', '--abbrev-ref', 'HEAD', cwd=cwd)
    return result or 'HEAD'


def is_clean(cwd: Path) -> bool:
    """
    检查工作区是否干净（无未提交更改）。

    Args:
        cwd: 工作目录

    Returns:
        True表示干净
    """
    result = git_command('status', '--porcelain', cwd=cwd)
    return result == '' if result is not None else False


def has_uncommitted_changes(cwd: Path) -> bool:
    """
    检查是否有未提交更改（staged或unstaged）。

    Args:
        cwd: 工作目录

    Returns:
        True表示有更改
    """
    return not is_clean(cwd)


def modified_files(cwd: Path) -> list[str]:
    """
    获取已修改文件列表（相对路径）。

    Args:
        cwd: 工作目录

    Returns:
        已修改文件的相对路径列表
    """
    result = git_command('diff', '--name-only', cwd=cwd)
    if not result:
        return []
    return [line.strip() for line in result.splitlines() if line.strip()]


# ============ Stash操作 ============

def stash_create(cwd: Path, message: str = '') -> str | None:
    """
    创建stash，返回stash ref。

    Args:
        cwd: 工作目录
        message: stash消息

    Returns:
        stash引用（如 'stash@{0}'），失败返回None
    """
    if is_clean(cwd):
        return None

    args = ['stash', 'push']
    if message:
        args.extend(['-m', message])

    result = git_command(*args, cwd=cwd)
    if result and 'No local changes' not in result:
        return 'stash@{0}'
    return None


def stash_pop(cwd: Path, stash_ref: str = '') -> bool:
    """
    恢复stash。

    Args:
        cwd: 工作目录
        stash_ref: stash引用，默认最近的stash

    Returns:
        是否成功
    """
    args = ['stash', 'pop']
    if stash_ref:
        args.append(stash_ref)

    result = git_command(*args, cwd=cwd, timeout=15)
    return result is not None


# ============ 提交操作 ============

def commit(cwd: Path, message: str, add_all: bool = False) -> str | None:
    """
    创建提交。

    Args:
        cwd: 工作目录
        message: 提交消息
        add_all: 是否先 git add -A

    Returns:
        提交哈希，失败返回None
    """
    if add_all:
        git_command('add', '-A', cwd=cwd)

    result = git_command('commit', '-m', message, cwd=cwd, timeout=15)
    if result is None:
        return None

    # 获取刚提交的哈希
    sha = git_command('rev-parse', '--short', 'HEAD', cwd=cwd)
    return sha


def diff_stat(cwd: Path, ref: str = 'HEAD') -> str:
    """
    获取与指定ref之间的diff统计。

    Args:
        cwd: 工作目录
        ref: 比较的git引用

    Returns:
        diff --stat输出文本
    """
    result = git_command('diff', '--stat', ref, cwd=cwd)
    return result or ''


# ============ WorktreeManager ============

@dataclass
class WorktreeInfo:
    """Worktree信息。"""
    path: Path
    branch: str
    head: str
    is_main: bool = False


class WorktreeManager:
    """
    Git Worktree管理器。为多Agent场景提供隔离的工作目录。

    用法::

        wm = WorktreeManager(repo_root)
        wt_path = wm.create('agent-java-dev')    # 创建worktree
        # ... Agent在wt_path中工作 ...
        wm.merge(wt_path)                         # 合并回主分支
        wm.remove(wt_path)                         # 清理worktree

    设计：
    - worktree目录统一放在 repo_root/.worktrees/ 下
    - 每个worktree对应一个独立分支
    - merge前自动检查冲突
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root.resolve()
        self._worktree_dir = self.repo_root / '.worktrees'

    def create(self, name: str, base_branch: str = 'main') -> Path:
        """
        创建worktree，返回路径。

        Args:
            name: worktree名称（也作为分支名前缀）
            base_branch: 基于哪个分支创建

        Returns:
            worktree目录路径

        Raises:
            RuntimeError: 创建失败
        """
        self._worktree_dir.mkdir(parents=True, exist_ok=True)

        branch_name = f'wt/{name}'
        wt_path = self._worktree_dir / name

        if wt_path.exists():
            raise RuntimeError(f'Worktree already exists: {wt_path}')

        result = git_command(
            'worktree', 'add', '-b', branch_name,
            str(wt_path), base_branch,
            cwd=self.repo_root,
            timeout=15,
        )

        if result is None:
            raise RuntimeError(f'Failed to create worktree: {name}')

        return wt_path

    def remove(self, worktree_path: Path) -> bool:
        """
        移除worktree及其分支。

        Args:
            worktree_path: worktree目录路径

        Returns:
            是否成功
        """
        worktree_path = worktree_path.resolve()

        # 获取分支名（用于后续删除）
        branch = current_branch(worktree_path)

        # 移除worktree
        result = git_command(
            'worktree', 'remove', '--force', str(worktree_path),
            cwd=self.repo_root,
            timeout=15,
        )

        if result is None:
            # 强制清理：手动删除目录并prune
            try:
                shutil.rmtree(str(worktree_path), ignore_errors=True)
            except OSError:
                pass
            git_command('worktree', 'prune', cwd=self.repo_root)

        # 删除对应分支（如果不是当前分支）
        if branch and branch.startswith('wt/'):
            git_command('branch', '-D', branch, cwd=self.repo_root)

        return True

    def merge(
        self,
        worktree_path: Path,
        target_branch: str = 'main',
    ) -> tuple[bool, str]:
        """
        将worktree分支合并到目标分支。

        Args:
            worktree_path: worktree目录路径
            target_branch: 目标分支名

        Returns:
            (是否成功, 消息)
        """
        worktree_path = worktree_path.resolve()
        wt_branch = current_branch(worktree_path)

        if wt_branch == 'HEAD':
            return False, 'Could not determine worktree branch'

        # 检查worktree是否有未提交更改
        if has_uncommitted_changes(worktree_path):
            return False, f'Worktree has uncommitted changes: {worktree_path}'

        # 在主仓库执行合并
        # 先切到目标分支
        cur = current_branch(self.repo_root)
        if cur != target_branch:
            result = git_command('checkout', target_branch, cwd=self.repo_root)
            if result is None:
                return False, f'Failed to checkout {target_branch}'

        result = git_command(
            'merge', '--no-ff', wt_branch,
            '-m', f'Merge {wt_branch} into {target_branch}',
            cwd=self.repo_root,
            timeout=30,
        )

        if result is None:
            # 合并冲突，中止
            git_command('merge', '--abort', cwd=self.repo_root)
            return False, f'Merge conflict: {wt_branch} -> {target_branch}'

        return True, f'Merged {wt_branch} into {target_branch}'

    def list_worktrees(self) -> list[dict[str, Any]]:
        """
        列出所有worktree。

        Returns:
            worktree信息列表
        """
        result = git_command(
            'worktree', 'list', '--porcelain',
            cwd=self.repo_root,
        )
        if not result:
            return []

        worktrees: list[dict[str, Any]] = []
        current: dict[str, Any] = {}

        for line in result.splitlines():
            line = line.strip()
            if not line:
                if current:
                    worktrees.append(current)
                    current = {}
                continue
            if line.startswith('worktree '):
                current['path'] = line[len('worktree '):]
            elif line.startswith('HEAD '):
                current['head'] = line[len('HEAD '):]
            elif line.startswith('branch '):
                # refs/heads/xxx -> xxx
                ref = line[len('branch '):]
                current['branch'] = ref.replace('refs/heads/', '')
            elif line == 'bare':
                current['bare'] = True
            elif line == 'detached':
                current['detached'] = True

        if current:
            worktrees.append(current)

        return worktrees

    def cleanup_stale(self) -> int:
        """
        清理已不存在的worktree引用。

        Returns:
            清理的数量
        """
        before = self.list_worktrees()
        git_command('worktree', 'prune', cwd=self.repo_root)
        after = self.list_worktrees()
        return len(before) - len(after)
