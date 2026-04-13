"""
插件系统
========
第三方扩展包，可打包skills、hooks、MCP servers、工具。
对标OpenHarness的plugins/loader.py。

设计：
- 每个插件 = 一个目录 + plugin.json清单
- 插件可包含：skills、hooks、MCP server配置、自定义工具模块
- PluginLoader发现并加载插件，注册到对应的子系统
- 低耦合：通过可选参数接收registry/config/manager，不强依赖
"""

from __future__ import annotations

import json
import importlib
import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .skills import SkillRegistry
    from .hooks import HookExecutor
    from .mcp_client import McpClientManager, McpServerConfig


# ============ 数据结构 ============

@dataclass
class PluginManifest:
    """
    插件清单（对应plugin.json）。

    示例plugin.json::

        {
            "name": "medical-compliance",
            "version": "1.0.0",
            "description": "医疗合规检查插件",
            "author": "harness-team",
            "skills": ["skills/"],
            "hooks": ["hooks/pre_check.py"],
            "mcp_servers": [
                {"name": "med-db", "command": "python", "args": ["server.py"]}
            ],
            "tools": ["tools/validator.py"]
        }
    """
    name: str
    version: str
    description: str
    author: str = ''
    skills: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)
    mcp_servers: list[dict[str, Any]] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


@dataclass
class LoadedPlugin:
    """已加载的插件记录。"""
    manifest: PluginManifest
    plugin_dir: Path
    loaded_skills: list[str] = field(default_factory=list)
    loaded_hooks: list[str] = field(default_factory=list)
    loaded_mcp_servers: list[str] = field(default_factory=list)
    loaded_tools: list[str] = field(default_factory=list)


# ============ 解析 ============

def parse_manifest(plugin_dir: Path) -> PluginManifest | None:
    """
    从plugin.json解析插件清单。

    Args:
        plugin_dir: 插件目录（包含plugin.json）

    Returns:
        PluginManifest或None（文件不存在或解析失败）
    """
    manifest_file = plugin_dir / 'plugin.json'
    if not manifest_file.is_file():
        return None

    try:
        text = manifest_file.read_text(encoding='utf-8')
        data = json.loads(text)
    except (OSError, json.JSONDecodeError):
        return None

    name = data.get('name', '')
    version = data.get('version', '')
    if not name or not version:
        return None

    return PluginManifest(
        name=name,
        version=version,
        description=data.get('description', ''),
        author=data.get('author', ''),
        skills=data.get('skills', []),
        hooks=data.get('hooks', []),
        mcp_servers=data.get('mcp_servers', []),
        tools=data.get('tools', []),
    )


# ============ PluginLoader ============

class PluginLoader:
    """
    插件加载器。

    发现来源：

    1. 项目目录 .harness/plugins/
    2. 用户目录 ~/.harness/plugins/

    用法::

        loader = PluginLoader()
        plugins = loader.discover(project_dir)
        for p in plugins:
            loader.load(p, plugin_dir)

    与子系统的集成通过构造函数的可选参数实现（低耦合）：
    - skill_registry: 注册skill
    - hook_config: 注册hook
    - mcp_manager: 注册MCP server
    """

    def __init__(
        self,
        skill_registry: SkillRegistry | None = None,
        hook_config: Any = None,
        mcp_manager: McpClientManager | None = None,
    ):
        self._skill_registry = skill_registry
        self._hook_config = hook_config
        self._mcp_manager = mcp_manager
        self._loaded: dict[str, LoadedPlugin] = {}

    def discover(self, *search_dirs: Path) -> list[tuple[PluginManifest, Path]]:
        """
        发现所有插件。

        在每个search_dir下查找包含plugin.json的子目录。

        Args:
            *search_dirs: 搜索目录列表

        Returns:
            [(PluginManifest, plugin_dir)] 列表
        """
        found: list[tuple[PluginManifest, Path]] = []
        for base_dir in search_dirs:
            if not base_dir.is_dir():
                continue
            try:
                for sub in sorted(base_dir.iterdir()):
                    if not sub.is_dir():
                        continue
                    manifest = parse_manifest(sub)
                    if manifest:
                        found.append((manifest, sub))
            except OSError:
                continue
        return found

    def discover_default(
        self,
        project_dir: Path | None = None,
    ) -> list[tuple[PluginManifest, Path]]:
        """
        使用默认路径发现插件。

        搜索顺序：
        1. ~/.harness/plugins/
        2. project_dir/.harness/plugins/

        Args:
            project_dir: 项目根目录

        Returns:
            [(PluginManifest, plugin_dir)] 列表
        """
        dirs: list[Path] = []

        # 用户级
        home_plugins = Path.home() / '.harness' / 'plugins'
        if home_plugins.is_dir():
            dirs.append(home_plugins)

        # 项目级
        if project_dir:
            proj_plugins = project_dir / '.harness' / 'plugins'
            if proj_plugins.is_dir():
                dirs.append(proj_plugins)

        return self.discover(*dirs)

    def load(self, manifest: PluginManifest, plugin_dir: Path) -> LoadedPlugin:
        """
        加载插件：注册其skills/hooks/mcp_servers/tools。

        Args:
            manifest: 插件清单
            plugin_dir: 插件目录

        Returns:
            LoadedPlugin记录
        """
        record = LoadedPlugin(manifest=manifest, plugin_dir=plugin_dir)

        # 加载skills
        record.loaded_skills = self._load_skills(manifest, plugin_dir)

        # 加载hooks
        record.loaded_hooks = self._load_hooks(manifest, plugin_dir)

        # 加载MCP servers
        record.loaded_mcp_servers = self._load_mcp_servers(manifest, plugin_dir)

        # 加载自定义工具模块
        record.loaded_tools = self._load_tools(manifest, plugin_dir)

        self._loaded[manifest.name] = record
        return record

    def load_all(
        self,
        plugins: list[tuple[PluginManifest, Path]],
    ) -> list[LoadedPlugin]:
        """
        批量加载插件。

        Args:
            plugins: discover()返回的列表

        Returns:
            已加载的插件记录列表
        """
        results = []
        for manifest, plugin_dir in plugins:
            record = self.load(manifest, plugin_dir)
            results.append(record)
        return results

    def list_plugins(self) -> list[dict[str, Any]]:
        """
        列出已加载的插件。

        Returns:
            插件信息列表
        """
        result = []
        for name, record in self._loaded.items():
            result.append({
                'name': record.manifest.name,
                'version': record.manifest.version,
                'description': record.manifest.description,
                'author': record.manifest.author,
                'dir': str(record.plugin_dir),
                'skills': record.loaded_skills,
                'hooks': record.loaded_hooks,
                'mcp_servers': record.loaded_mcp_servers,
                'tools': record.loaded_tools,
            })
        return result

    def is_loaded(self, plugin_name: str) -> bool:
        """检查插件是否已加载。"""
        return plugin_name in self._loaded

    @property
    def count(self) -> int:
        """已加载插件数量。"""
        return len(self._loaded)

    # ---- 内部加载方法 ----

    def _load_skills(self, manifest: PluginManifest, plugin_dir: Path) -> list[str]:
        """加载插件的skill目录到SkillRegistry。"""
        if not manifest.skills or self._skill_registry is None:
            return []

        loaded: list[str] = []
        for skill_path_str in manifest.skills:
            skill_dir = plugin_dir / skill_path_str
            if skill_dir.is_dir():
                before = self._skill_registry.count
                self._skill_registry.discover(skill_dir)
                after = self._skill_registry.count
                if after > before:
                    loaded.append(str(skill_dir))
        return loaded

    def _load_hooks(self, manifest: PluginManifest, plugin_dir: Path) -> list[str]:
        """
        加载插件的hook脚本。

        hook脚本约定：Python文件，包含 pre_tool 和/或 post_tool 函数。
        加载方式：动态import模块，读取其中的hook函数。
        """
        if not manifest.hooks:
            return []

        loaded: list[str] = []
        for hook_path_str in manifest.hooks:
            hook_file = plugin_dir / hook_path_str
            if not hook_file.is_file():
                continue

            module = _import_module_from_path(
                f'harness_plugin_{manifest.name}_{hook_file.stem}',
                hook_file,
            )
            if module is not None:
                loaded.append(str(hook_file))
                # 如果有hook_config，注册hook函数
                if self._hook_config is not None:
                    pre = getattr(module, 'pre_tool', None)
                    post = getattr(module, 'post_tool', None)
                    if pre and hasattr(self._hook_config, 'pre_tool'):
                        if isinstance(self._hook_config.pre_tool, list):
                            self._hook_config.pre_tool.append(pre)
                    if post and hasattr(self._hook_config, 'post_tool'):
                        if isinstance(self._hook_config.post_tool, list):
                            self._hook_config.post_tool.append(post)

        return loaded

    def _load_mcp_servers(
        self,
        manifest: PluginManifest,
        plugin_dir: Path,
    ) -> list[str]:
        """加载插件的MCP Server配置到McpClientManager。"""
        if not manifest.mcp_servers or self._mcp_manager is None:
            return []

        # 延迟导入，避免循环依赖
        from .mcp_client import McpServerConfig

        loaded: list[str] = []
        for server_cfg in manifest.mcp_servers:
            if not isinstance(server_cfg, dict):
                continue
            name = server_cfg.get('name', '')
            command = server_cfg.get('command', '')
            if not name or not command:
                continue

            config = McpServerConfig(
                name=f'{manifest.name}.{name}',
                command=command,
                args=server_cfg.get('args', []),
                env=server_cfg.get('env', {}),
                cwd=str(plugin_dir),
            )
            self._mcp_manager.add_server(config)
            loaded.append(config.name)

        return loaded

    def _load_tools(self, manifest: PluginManifest, plugin_dir: Path) -> list[str]:
        """
        加载插件的自定义工具模块。

        工具模块约定：Python文件，包含继承BaseTool的类。
        这里只做import，具体注册留给调用方。
        """
        if not manifest.tools:
            return []

        loaded: list[str] = []
        for tool_path_str in manifest.tools:
            tool_file = plugin_dir / tool_path_str
            if not tool_file.is_file():
                continue

            module = _import_module_from_path(
                f'harness_plugin_{manifest.name}_{tool_file.stem}',
                tool_file,
            )
            if module is not None:
                loaded.append(str(tool_file))

        return loaded


# ============ 辅助函数 ============

def _import_module_from_path(module_name: str, file_path: Path) -> Any:
    """
    从文件路径动态导入Python模块。

    Args:
        module_name: 模块名（用于sys.modules注册）
        file_path: .py文件路径

    Returns:
        模块对象，导入失败返回None
    """
    try:
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception:
        return None
