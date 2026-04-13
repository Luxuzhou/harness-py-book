"""
Skill系统
=========
Markdown文件定义的可加载技能。
支持YAML frontmatter元数据、按需加载、progressive disclosure。
对标OpenHarness的skills/loader.py。

设计：
- Skill = 一个SKILL.md文件，包含YAML frontmatter + 正文
- 三级发现源：项目 > 用户 > 内置
- list_skills()只返回元数据（省token），get_skill()按需加载正文
- 纯标准库，不依赖PyYAML（手写简易YAML解析）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============ 数据结构 ============

@dataclass
class SkillDefinition:
    """一个Skill的定义。"""
    name: str
    description: str
    version: str
    content: str              # SKILL.md的完整正文（不含frontmatter）
    file_path: Path
    tags: list[str] = field(default_factory=list)


# ============ Frontmatter解析 ============

_FRONTMATTER_RE = re.compile(
    r'\A---\s*\n(.*?)\n---\s*\n(.*)',
    re.DOTALL,
)


def parse_skill_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """
    解析SKILL.md的YAML frontmatter和正文。

    支持的frontmatter格式（简易YAML子集）::

        ---
        name: commit
        description: Git commit with good message
        version: "1.0"
        tags: [git, workflow]
        ---

    Args:
        text: SKILL.md的完整文本

    Returns:
        (元数据dict, 正文str)
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    yaml_block = match.group(1)
    body = match.group(2)

    meta = _parse_simple_yaml(yaml_block)
    return meta, body


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """
    解析简易YAML（仅支持顶层键值对和列表）。

    不引入PyYAML依赖。支持：
    - key: value
    - key: "quoted value"
    - key: [item1, item2]
    """
    result: dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        colon_idx = line.find(':')
        if colon_idx < 1:
            continue

        key = line[:colon_idx].strip()
        val = line[colon_idx + 1:].strip()

        # 处理列表 [a, b, c]
        if val.startswith('[') and val.endswith(']'):
            items = val[1:-1].split(',')
            result[key] = [_unquote(item.strip()) for item in items if item.strip()]
        else:
            result[key] = _unquote(val)

    return result


def _unquote(s: str) -> str:
    """去除引号。"""
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        return s[1:-1]
    return s


# ============ SkillRegistry ============

# Skill文件名模式
_SKILL_GLOB = 'SKILL.md'
_SKILL_GLOB_ALT = '*.skill.md'


class SkillRegistry:
    """
    Skill注册表。

    发现来源（按优先级）：

    1. 项目目录 .claude/skills/
    2. 用户目录 ~/.claude/skills/
    3. 内置skills/ 目录

    同名skill，高优先级覆盖低优先级。

    用法::

        registry = SkillRegistry()
        registry.discover(project_dir)
        skills = registry.list_skills()           # 只返回name+description
        full = registry.get_skill('commit')       # 按需加载完整内容
    """

    def __init__(self):
        self._skills: dict[str, SkillDefinition] = {}
        self._search_dirs: list[Path] = []

    def discover(self, *search_dirs: Path) -> int:
        """
        从目录中发现SKILL.md文件。

        搜索每个目录下的 SKILL.md 和 *.skill.md 文件。
        后发现的同名skill覆盖先发现的（实现优先级）。

        Args:
            *search_dirs: 搜索目录列表，按优先级从低到高

        Returns:
            发现的skill总数
        """
        self._search_dirs.extend(search_dirs)

        for base_dir in search_dirs:
            if not base_dir.is_dir():
                continue
            self._scan_directory(base_dir)

        return len(self._skills)

    def discover_default(self, project_dir: Path | None = None) -> int:
        """
        使用默认搜索路径发现skill。

        搜索顺序（低优先级在前）：
        1. 内置 skills/ 目录
        2. ~/.claude/skills/
        3. 项目 .claude/skills/

        Args:
            project_dir: 项目根目录

        Returns:
            发现的skill总数
        """
        dirs: list[Path] = []

        # 内置
        builtin = Path(__file__).parent / 'skills'
        if builtin.is_dir():
            dirs.append(builtin)

        # 用户级
        home_skills = Path.home() / '.claude' / 'skills'
        if home_skills.is_dir():
            dirs.append(home_skills)

        # 项目级（最高优先级）
        if project_dir:
            project_skills = project_dir / '.claude' / 'skills'
            if project_skills.is_dir():
                dirs.append(project_skills)

        return self.discover(*dirs)

    def list_skills(self) -> list[dict[str, Any]]:
        """
        列出所有skill的元数据（不含正文，省token）。

        Returns:
            skill元数据列表
        """
        result = []
        for skill in self._skills.values():
            result.append({
                'name': skill.name,
                'description': skill.description,
                'version': skill.version,
                'tags': skill.tags,
                'file': str(skill.file_path),
            })
        return result

    def get_skill(self, name: str) -> SkillDefinition | None:
        """
        获取完整skill内容。

        Args:
            name: skill名称

        Returns:
            SkillDefinition或None
        """
        return self._skills.get(name)

    def get_skill_prompt(self, name: str) -> str:
        """
        获取skill内容作为prompt注入文本。

        格式::

            <skill name="commit" version="1.0">
            [skill正文内容]
            </skill>

        Args:
            name: skill名称

        Returns:
            格式化的prompt文本，skill不存在则返回空串
        """
        skill = self._skills.get(name)
        if skill is None:
            return ''
        return (
            f'<skill name="{skill.name}" version="{skill.version}">\n'
            f'{skill.content}\n'
            f'</skill>'
        )

    def names(self) -> list[str]:
        """获取所有已注册的skill名称。"""
        return list(self._skills.keys())

    @property
    def count(self) -> int:
        """已注册skill数量。"""
        return len(self._skills)

    # ---- 内部方法 ----

    def _scan_directory(self, base_dir: Path):
        """扫描目录下的skill文件。"""
        # 直接放在目录下的 SKILL.md
        skill_file = base_dir / _SKILL_GLOB
        if skill_file.is_file():
            self._load_skill_file(skill_file)

        # 子目录下的 SKILL.md
        try:
            for sub in sorted(base_dir.iterdir()):
                if sub.is_dir():
                    f = sub / _SKILL_GLOB
                    if f.is_file():
                        self._load_skill_file(f)
        except OSError:
            pass

        # *.skill.md 文件
        try:
            for f in sorted(base_dir.glob(_SKILL_GLOB_ALT)):
                if f.is_file():
                    self._load_skill_file(f)
        except OSError:
            pass

    def _load_skill_file(self, file_path: Path):
        """加载单个skill文件。"""
        try:
            text = file_path.read_text(encoding='utf-8')
        except OSError:
            return

        meta, body = parse_skill_frontmatter(text)

        # 如果frontmatter没有name，用父目录名或文件名
        name = meta.get('name', '')
        if not name:
            if file_path.name == _SKILL_GLOB:
                name = file_path.parent.name
            else:
                # xxx.skill.md -> xxx
                name = file_path.stem.replace('.skill', '')

        if not name:
            return

        tags = meta.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',')]

        skill = SkillDefinition(
            name=name,
            description=meta.get('description', ''),
            version=str(meta.get('version', '0.1')),
            content=body.strip(),
            file_path=file_path,
            tags=tags,
        )
        self._skills[name] = skill
