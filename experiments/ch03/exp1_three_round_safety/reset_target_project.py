"""把 target_project/ 复位到 _fixtures/target_project_pristine/ 的干净状态。

为什么需要：
  Agent 跑一轮会在 target_project 里写测试文件、改源码、建新目录。如果不
  复位，下一次运行 Agent 面对的是"上一轮的遗留"，实验结果就失去可比性
  （所有档位看到同一个被污染的初始状态，层间差异无法显现）。

两种用法：
  1. 被 run_bare / run_harnessed / run_progressive 脚本自动调用，每次启动
     强制复位。
  2. 读者手动调用：python reset_target_project.py

设计原则：
  - fixture 目录（_fixtures/target_project_pristine/）是**只读**的真相源，
    任何时候都可以从它复制一份干净的 target_project。
  - reset 是**幂等**的：连续调用 N 次的效果和调用 1 次一样。
  - 不依赖 git：读者就算用 zip 下载仓库也能工作。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PRISTINE = _HERE / '_fixtures' / 'target_project_pristine'
_WORK = _HERE / 'target_project'


def reset_to_pristine(verbose: bool = True) -> Path:
    """rmtree target_project + copytree from fixture。返回复位后的 target_project 路径。"""
    if not _PRISTINE.exists():
        raise FileNotFoundError(
            f'找不到 pristine fixture: {_PRISTINE}\n'
            f'仓库可能不完整。请从 git 拉取 _fixtures/ 目录，或联系作者。'
        )

    if _WORK.exists():
        shutil.rmtree(_WORK)
    shutil.copytree(_PRISTINE, _WORK)

    # target_project_backup 是 run_progressive.py 老流程留下的临时备份，
    # 新流程不用，顺手清掉避免读者误以为它是干净源。
    old_backup = _HERE / 'target_project_backup'
    if old_backup.exists():
        shutil.rmtree(old_backup)

    if verbose:
        print(f'[reset] target_project ← {_PRISTINE.relative_to(_HERE)}')
    return _WORK


if __name__ == '__main__':
    reset_to_pristine()
    print('[reset] done')
    sys.exit(0)
