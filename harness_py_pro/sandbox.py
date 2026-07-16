"""
沙箱隔离
========
框架级安全边界。从"规则告诉Agent不要做"升级为"执行环境让Agent做不到"。

对标：
- Claude Code: Permission Modes + Sandbox Mode
- Codex: Docker容器隔离（每任务独立容器，默认禁外网）
- OpenHarness: Sandbox settings (network/filesystem restrictions)

三层防御：
  Layer 1 — 规则层（CLAUDE.md、prompt指令）：Agent可能忽略
  Layer 2 — 检查层（permissions.py、hooks.py）：代码级拦截，但工具内部可绕过
  Layer 3 — 沙箱层（本模块）：执行环境级隔离，无法绕过  ← 这是本模块的定位

设计原则：
  deny-by-default — 默认禁止，显式允许
  最小权限 — 只开放任务必需的能力
  不信任工具输出 — 沙箱不依赖Agent的"好意"

四个组件：
  1. PermissionMode — 四种授权模式
  2. NetworkPolicy — 网络隔离策略
  3. FilesystemPolicy — 文件系统隔离策略
  4. Sandbox — 组合策略，提供受限执行环境
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import shutil
import threading
import queue
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .pathing import resolve_agent_path


# ============ 权限模式 ============

class PermissionMode(Enum):
    """
    四种权限模式。对标Claude Code的permission modes。

    ASK       — 每次写操作/命令执行前请求确认（默认）
    ACCEPT    — 自动批准文件编辑，命令仍需确认
    BYPASS    — 全自动，不确认（仅限可信环境）
    PLAN      — 规划模式，只允许只读操作
    """
    ASK = 'ask'
    ACCEPT = 'accept_edits'
    BYPASS = 'bypass'
    PLAN = 'plan'


def _call_confirm_with_timeout(
    confirm_fn: Any, action: str, detail: str, timeout: int,
) -> tuple[bool, str]:
    """
    带超时的用户确认调用。超时默认拒绝（fail-closed），避免 Agent 在无人值守
    场景下因 confirm_fn 永远阻塞而卡死。
    """
    if timeout is None or timeout <= 0:
        # 显式关掉超时，恢复阻塞语义
        try:
            allowed = bool(confirm_fn(action, detail))
        except Exception as e:
            return False, f'confirm_fn 异常: {type(e).__name__}: {e}'
        return allowed, '' if allowed else '用户拒绝'

    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(confirm_fn, action, detail)
            allowed = bool(future.result(timeout=timeout))
        return allowed, '' if allowed else '用户拒绝'
    except concurrent.futures.TimeoutError:
        return False, f'用户确认超时（{timeout}s），已拒绝'
    except Exception as e:
        return False, f'confirm_fn 异常: {type(e).__name__}: {e}'


def check_permission(
    mode: PermissionMode,
    action: str,
    detail: str = '',
    *,
    confirm_fn: Any = None,
    confirm_timeout: int = 30,
) -> tuple[bool, str]:
    """
    根据权限模式检查操作是否允许。

    action: 'read' | 'write' | 'edit' | 'execute' | 'network'
    confirm_fn: 可选的用户确认回调 (action, detail) -> bool
    confirm_timeout: 调用 confirm_fn 的超时秒数；超时按"拒绝"处理。
        设为 0 或负数表示禁用超时（恢复阻塞语义）。默认 30s 是"人类正常操作
        + 短暂走神"的合理上限；大于这个时长 Agent 应自己决定继续还是停。

    返回 (allowed, reason)
    """
    # PLAN模式：只允许读
    if mode == PermissionMode.PLAN:
        if action == 'read':
            return True, ''
        return False, f'规划模式下不允许 {action} 操作'

    # BYPASS模式：全部允许
    if mode == PermissionMode.BYPASS:
        return True, ''

    # ACCEPT模式：读写自动批准，命令需确认
    if mode == PermissionMode.ACCEPT:
        if action in ('read', 'write', 'edit'):
            return True, ''
        # execute/network需要确认
        if confirm_fn:
            return _call_confirm_with_timeout(
                confirm_fn, action, detail, confirm_timeout)
        return False, '需要用户确认但未配置confirm_fn'

    # ASK模式：读自动批准，其余需确认
    if mode == PermissionMode.ASK:
        if action == 'read':
            return True, ''
        if confirm_fn:
            return _call_confirm_with_timeout(
                confirm_fn, action, detail, confirm_timeout)
        return False, '需要用户确认但未配置confirm_fn'

    return True, ''


# ============ 网络隔离 ============

# 危险网络命令（在bash中拦截）
NETWORK_COMMANDS = frozenset({
    'curl', 'wget', 'ping', 'ssh', 'scp', 'sftp', 'ftp',
    'nc', 'netcat', 'telnet', 'nmap', 'dig', 'nslookup',
    'rsync', 'rclone',
})

POWERSHELL_NETWORK_COMMANDS = frozenset({
    'invoke-webrequest', 'invoke-restmethod', 'iwr', 'irm', 'start-bitstransfer',
})

# 危险Python网络模块（在脚本内容中扫描）
NETWORK_MODULES = frozenset({
    'requests', 'urllib', 'urllib3', 'httpx', 'aiohttp',
    'socket', 'http.client', 'http.server',
    'smtplib', 'ftplib', 'paramiko',
})

# 网络相关环境变量（从subprocess中移除）
NETWORK_ENV_VARS = frozenset({
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY',
    'http_proxy', 'https_proxy', 'all_proxy',
    'NO_PROXY', 'no_proxy',
})

COMMAND_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*")
PARENT_TRAVERSAL_RE = re.compile(r'(^|[\s\'"=])\.\.(?:[\\/]|$)')
WINDOWS_ABS_PATH_RE = re.compile(r'(^|[\s\'"=])([A-Za-z]:[\\/][^\s\'"|&;<>]+)')
COMMAND_PATH_TOKEN_RE = re.compile(r'(?:^|[\s\'"=])([^\s\'"|&;<>]*\.\.(?:[\\/][^\s\'"|&;<>]*)?)')


@dataclass
class NetworkPolicy:
    """
    网络隔离策略。

    deny_by_default=True时，所有网络访问被禁止。
    可通过allowed_hosts白名单开放特定域名。
    """
    deny_by_default: bool = True
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)

    def check_command(self, command: str) -> tuple[bool, str]:
        """检查命令是否涉及网络访问。"""
        if not self.deny_by_default:
            return True, ''

        command = command.strip()
        if not command:
            return True, ''

        allowed_commands = {item.lower() for item in self.allowed_commands}
        tokens = {token.lower() for token in COMMAND_TOKEN_RE.findall(command)}
        blocked_commands = (NETWORK_COMMANDS | POWERSHELL_NETWORK_COMMANDS) - allowed_commands
        hit = next((token for token in blocked_commands if token in tokens), None)
        if hit:
            return False, f'网络隔离: 禁止执行 {hit}'

        for mod in NETWORK_MODULES:
            escaped = re.escape(mod)
            patterns = (
                rf'\bimport\s+{escaped}\b',
                rf'\bfrom\s+{escaped}\b',
                rf'__import__\(\s*[\'"]{escaped}[\'"]\s*\)',
                rf'importlib\.import_module\(\s*[\'"]{escaped}[\'"]\s*\)',
            )
            if any(re.search(pattern, command) for pattern in patterns):
                return False, f'网络隔离: 禁止导入 {mod}'

        return True, ''

    def check_script_content(self, content: str) -> tuple[bool, str]:
        """检查脚本内容是否包含网络操作。"""
        if not self.deny_by_default:
            return True, ''

        for mod in NETWORK_MODULES:
            if re.search(rf'^\s*(import\s+{mod}|from\s+{mod})', content, re.MULTILINE):
                return False, f'网络隔离: 脚本包含网络模块 {mod}'

        return True, ''

    def get_clean_env(self, base_env: dict | None = None) -> dict:
        """获取移除了代理变量的干净环境。"""
        env = dict(base_env or os.environ)
        if self.deny_by_default:
            for var in NETWORK_ENV_VARS:
                env.pop(var, None)
        return env


# ============ 文件系统隔离 ============

# 始终保护的敏感路径（对齐Claude Code）
SENSITIVE_PATHS = [
    '**/.ssh/*',
    '**/.aws/credentials',
    '**/.azure/*',
    '**/.gnupg/*',
    '**/.docker/config.json',
    '**/.kube/config',
    '**/.npmrc',
    '**/.pypirc',
    '**/.netrc',
    '**/credentials.json',
    '**/.git/config',
]

# 敏感路径段（跨平台匹配用，统一正斜杠）
SENSITIVE_SEGMENTS = [
    '/.ssh/',
    '/.aws/credentials',
    '/.azure/',
    '/.gnupg/',
    '/.docker/config.json',
    '/.kube/config',
    '/.npmrc',
    '/.pypirc',
    '/.netrc',
    '/credentials.json',
    '/.git/config',
]

# 始终禁止的危险命令模式
DANGEROUS_COMMANDS = [
    re.compile(r'\brm\s+(-[rf]+\s+)*(\/|\.|\*)', re.I),   # rm -rf / . *
    re.compile(r'\brmdir\s+/', re.I),                     # rmdir /
    re.compile(r'\bmkfs\b', re.I),                        # mkfs
    re.compile(r'\bdd\s+.*of=/dev/', re.I),               # dd of=/dev/
    re.compile(r'\bchmod\s+-R\s+777\s+/', re.I),          # chmod -R 777 /
    re.compile(r'\bchown\s+-R\s+.*\s+/', re.I),           # chown -R ... /
    re.compile(r'>\s*/dev/sd', re.I),                      # > /dev/sda
    re.compile(r'\bgit\s+push\s+.*--force\b', re.I),      # git push --force
    re.compile(r'\bgit\s+reset\s+--hard\b', re.I),        # git reset --hard
]


@dataclass
class FilesystemPolicy:
    """
    文件系统隔离策略。

    allowed_roots: 允许访问的根目录列表（为空则不限制）
    denied_patterns: 额外的拒绝模式（glob格式）
    denied_filenames: 文件名级精细拒绝（不依赖路径前缀，比如 ".env"、"id_rsa"
        总是拒绝，无论目录在哪里）
    read_only_paths: 只允许读取不允许写入的路径
    block_symlinks: 是否拒绝任何符号链接，避免 symlink-to-/etc/passwd 这类绕过
    max_file_size_bytes: 写入时拦截过大文件，预防 zip 炸弹/内存炸弹
    """
    allowed_roots: list[Path] = field(default_factory=list)
    denied_patterns: list[str] = field(default_factory=list)
    denied_filenames: list[str] = field(default_factory=lambda: [
        '.env', '.env.local', '.env.production',
        'id_rsa', 'id_ed25519', 'id_ecdsa',
        '.aws/credentials', '.git-credentials', '.npmrc', '.pypirc',
        'kubeconfig', '.kube/config',
    ])
    read_only_paths: list[Path] = field(default_factory=list)
    block_sensitive: bool = True
    block_symlinks: bool = True
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50MB

    def check_path(self, path: Path, action: str = 'read') -> tuple[bool, str]:
        """检查路径访问是否允许。"""
        # Layer 0: 符号链接拦截（在 resolve() 之前判断，否则 resolve 会跟随链接）
        if self.block_symlinks:
            try:
                if path.is_symlink():
                    return False, f'符号链接拦截: {path}'
            except OSError:
                # is_symlink 在路径不存在时也可能抛 OSError，忽略让后续检查继续
                pass

        resolved = str(path.resolve())
        # 统一为正斜杠以便跨平台匹配
        resolved_unix = resolved.replace('\\', '/')

        # Layer 1: 敏感路径（不可覆盖）
        if self.block_sensitive:
            for segment in SENSITIVE_SEGMENTS:
                if segment in resolved_unix:
                    return False, f'敏感路径保护: {path}'

        # Layer 1.5: 文件名级拒绝（无论在哪个目录）
        for denied_name in self.denied_filenames:
            if resolved_unix.endswith('/' + denied_name) or resolved_unix.endswith(denied_name):
                # 精确匹配文件名，避免误伤同前缀文件（如 .envoy 不应命中 .env）
                if path.name == denied_name or resolved_unix.endswith('/' + denied_name):
                    return False, f'敏感文件名拦截: {path.name}'

        # Layer 2: allowed_roots白名单
        if self.allowed_roots:
            in_allowed = False
            resolved_path = path.resolve()
            for root in self.allowed_roots:
                try:
                    resolved_path.relative_to(root.resolve())
                    in_allowed = True
                    break
                except ValueError:
                    continue
            if not in_allowed:
                return False, f'文件系统隔离: {path} 不在允许的根目录内'

        # Layer 3: denied_patterns黑名单
        for pattern in self.denied_patterns:
            if pattern in resolved or path.match(pattern):
                return False, f'路径被禁止: {path} 匹配 {pattern}'

        # Layer 4: 只读路径
        if action in ('write', 'edit') and self.read_only_paths:
            resolved_path = path.resolve()
            for ro_path in self.read_only_paths:
                try:
                    resolved_path.relative_to(ro_path.resolve())
                    return False, f'只读路径: {path}'
                except ValueError:
                    continue

        # Layer 5: 文件大小（写入场景预防内存炸弹）
        if action in ('write', 'edit') and path.exists():
            try:
                if path.stat().st_size > self.max_file_size_bytes:
                    return False, (f'文件超过大小上限 {self.max_file_size_bytes // 1024 // 1024}MB: '
                                   f'{path}')
            except OSError:
                pass

        return True, ''

    def check_command(self, command: str) -> tuple[bool, str]:
        """检查命令是否包含危险操作。"""
        for pattern in DANGEROUS_COMMANDS:
            if pattern.search(command):
                return False, f'危险命令拦截: {command[:80]}'

        if PARENT_TRAVERSAL_RE.search(command):
            if not self.allowed_roots:
                return False, '文件系统隔离: command contains parent-directory traversal'
            matched_parent_path = False
            for raw_token in COMMAND_PATH_TOKEN_RE.findall(command):
                matched_parent_path = True
                token = raw_token.strip('\'"')
                if '..' not in Path(token).parts and '..' not in token.replace('\\', '/').split('/'):
                    continue
                candidate = self.allowed_roots[0] / token
                ok, _ = self.check_path(candidate, 'read')
                if not ok:
                    return False, f'文件系统隔离: parent traversal outside allowed roots: {token}'
            if not matched_parent_path:
                return False, '文件系统隔离: command contains unparseable parent-directory traversal'

        for match in WINDOWS_ABS_PATH_RE.finditer(command):
            candidate = Path(match.group(2))
            ok, _ = self.check_path(candidate, 'read')
            if not ok:
                return False, f'文件系统隔离: absolute path not allowed: {candidate}'
        return True, ''


# ============ 沙箱 ============

@dataclass
class Sandbox:
    """
    沙箱执行环境。组合网络、文件系统、权限策略。

    用法：
        sandbox = Sandbox(
            cwd=project_dir,
            permission_mode=PermissionMode.ACCEPT,
            network=NetworkPolicy(deny_by_default=True),
            filesystem=FilesystemPolicy(allowed_roots=[project_dir]),
        )

        # 检查操作
        ok, reason = sandbox.check_tool_call('bash', {'command': 'curl evil.com'})

        # 受限执行
        ok, output = sandbox.execute_command('python -m pytest', timeout=60)
    """
    cwd: Path = field(default_factory=Path.cwd)
    permission_mode: PermissionMode = PermissionMode.ASK
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    filesystem: FilesystemPolicy = field(default_factory=lambda: FilesystemPolicy())
    confirm_fn: Any = None

    # 统计
    _checks: int = 0
    _blocks: int = 0

    def check_tool_call(self, tool_name: str, tool_args: dict) -> tuple[bool, str]:
        """
        综合检查一次工具调用是否被沙箱允许。

        串联检查顺序（任一失败即拒绝）：
        1. 权限模式
        2. 文件系统策略
        3. 网络策略
        4. 危险命令检查
        """
        self._checks += 1

        # 确定action类型
        action = _tool_to_action(tool_name)

        # 1. 权限模式检查
        detail = f'{tool_name}({_brief_args(tool_args)})'
        ok, reason = check_permission(self.permission_mode, action, detail, confirm_fn=self.confirm_fn)
        if not ok:
            self._blocks += 1
            return False, reason

        # 2. 文件系统检查
        path_arg = tool_args.get('path', '')
        if path_arg:
            full_path = resolve_agent_path(
                self.cwd,
                path_arg,
                allowed_roots=self.filesystem.allowed_roots,
            )
            ok, reason = self.filesystem.check_path(full_path, action)
            if not ok:
                self._blocks += 1
                return False, reason

        # 3. 网络 + 危险命令检查（仅bash工具）
        if tool_name == 'bash':
            command = tool_args.get('command', '')

            ok, reason = self.network.check_command(command)
            if not ok:
                self._blocks += 1
                return False, reason

            ok, reason = self.filesystem.check_command(command)
            if not ok:
                self._blocks += 1
                return False, reason

        # 4. write_file内容中的网络模块检查
        if tool_name == 'write_file':
            content = tool_args.get('content', '')
            path = tool_args.get('path', '')
            if path.endswith('.py'):
                ok, reason = self.network.check_script_content(content)
                if not ok:
                    self._blocks += 1
                    return False, reason

        return True, ''

    def execute_command(
        self,
        command: str,
        *,
        timeout: int = 120,
    ) -> tuple[bool, str]:
        """
        在沙箱中执行命令。

        与直接subprocess.run的区别：
        1. 清除代理环境变量（网络隔离）
        2. 限制cwd到allowed_roots
        3. 命令预检（危险命令+网络命令）
        """
        # 预检
        ok, reason = self.filesystem.check_command(command)
        if not ok:
            return False, reason

        ok, reason = self.network.check_command(command)
        if not ok:
            return False, reason

        # 构建干净环境
        env = self.network.get_clean_env()
        # 确保UTF-8
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'

        # 执行
        # On Windows, prefer the native shell. Git Bash/MSYS can pick up the
        # Unix `mvn` shim and break Maven with missing classworlds jars even
        # when the same command succeeds from PowerShell/cmd.
        bash_path = None if sys.platform == 'win32' else _find_best_bash()
        try:
            if bash_path:
                proc = subprocess.Popen(
                    [bash_path, '-c', command],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=str(self.cwd), env=env,
                )
            else:
                proc = subprocess.Popen(
                    command, shell=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=str(self.cwd), env=env,
                )

            stdout, stderr = _threaded_communicate(proc, timeout)
            output = _smart_decode(stdout)
            errors = _smart_decode(stderr)

            combined = output
            if errors:
                combined += f'\n[stderr]\n{errors}'

            return proc.returncode == 0, combined[:10000]

        except subprocess.TimeoutExpired:
            proc.kill()
            return False, f'沙箱: 命令超时 ({timeout}s)'
        except Exception as e:
            return False, f'沙箱执行失败: {e}'

    @property
    def stats(self) -> dict:
        return {
            'checks': self._checks,
            'blocks': self._blocks,
            'mode': self.permission_mode.value,
            'network_isolated': self.network.deny_by_default,
            'fs_roots': [str(r) for r in self.filesystem.allowed_roots],
        }


# ============ 工厂函数 ============

def create_sandbox(
    cwd: Path,
    *,
    mode: str = 'ask',
    network_isolated: bool = True,
    allowed_roots: list[Path] | None = None,
    read_only_paths: list[Path] | None = None,
) -> Sandbox:
    """
    便捷创建沙箱。

    mode: 'ask' | 'accept' | 'bypass' | 'plan'
    """
    mode_enum = PermissionMode(mode)

    roots = allowed_roots or [cwd]
    fs_policy = FilesystemPolicy(
        allowed_roots=roots,
        read_only_paths=read_only_paths or [],
    )
    net_policy = NetworkPolicy(deny_by_default=network_isolated)

    return Sandbox(
        cwd=cwd,
        permission_mode=mode_enum,
        network=net_policy,
        filesystem=fs_policy,
    )


def create_docker_sandbox_command(
    command: str,
    cwd: Path,
    *,
    image: str = 'python:3.12-slim',
    network: bool = False,
    memory_limit: str = '512m',
    cpu_limit: float = 1.0,
    timeout: int = 300,
    pids_limit: int = 256,
    hardened: bool = True,
) -> str:
    """
    生成 Docker 沙箱命令。对标 Codex 的容器隔离模型。

    返回一个 docker run 命令字符串，可直接执行。适用于高安全要求场景
    （如生产环境、多租户、untrusted code）。

    `hardened=True`（默认）启用四项常见加固：
      --read-only                   根文件系统只读
      --tmpfs=/tmp:rw,noexec,...    /tmp 走 tmpfs 且禁止可执行
      --security-opt=no-new-privileges:true  禁止 setuid 提权
      --cap-drop=ALL                删除所有 Linux capabilities

    生产环境强烈建议保留 `hardened=True`；只有跑老脚本（依赖写根文件系统、
    依赖某个 capability）时才显式关掉。
    """
    parts: list[str] = [
        'docker', 'run', '--rm',
        f'--memory={memory_limit}',
        f'--memory-swap={memory_limit}',  # 与 memory 等值禁止 swap
        f'--cpus={cpu_limit}',
        f'--pids-limit={pids_limit}',
        '-v', f'{cwd}:/workspace',
        '-w', '/workspace',
    ]

    if not network:
        parts.append('--network=none')

    if hardened:
        parts.extend([
            '--read-only',
            '--tmpfs=/tmp:rw,noexec,nosuid,size=128m',
            '--security-opt=no-new-privileges:true',
            '--cap-drop=ALL',
        ])

    inner_command = command
    if timeout > 0 and sys.platform != 'win32':
        inner_command = f'timeout {int(timeout)}s bash -lc {shlex.quote(command)}'

    command_parts = [str(p) for p in parts if p]
    command_parts.extend([image, 'sh', '-lc', inner_command])
    return shlex.join(command_parts)


# ============ 辅助函数 ============

def _tool_to_action(tool_name: str) -> str:
    """工具名映射到操作类型。"""
    if tool_name in ('read_file', 'grep_search', 'glob_search'):
        return 'read'
    if tool_name == 'write_file':
        return 'write'
    if tool_name == 'edit_file':
        return 'edit'
    if tool_name == 'bash':
        return 'execute'
    return 'read'


def _brief_args(args: dict) -> str:
    """简要描述工具参数。"""
    if 'path' in args:
        return args['path']
    if 'command' in args:
        return args['command'][:60]
    if 'pattern' in args:
        return args['pattern']
    return str(args)[:60]


def _find_best_bash() -> str | None:
    if sys.platform != 'win32':
        return shutil.which('bash')
    for p in [r'C:\Program Files\Git\bin\bash.exe', r'C:\Program Files (x86)\Git\bin\bash.exe']:
        if os.path.exists(p):
            return p
    found = shutil.which('bash')
    if found and 'WindowsApps' not in found:
        return found
    return None


def _threaded_communicate(proc: subprocess.Popen, timeout: int) -> tuple[bytes, bytes]:
    stdout_q: queue.Queue[bytes] = queue.Queue()
    stderr_q: queue.Queue[bytes] = queue.Queue()

    def read_stream(stream, q):
        try:
            q.put(stream.read() or b'')
        except Exception:
            q.put(b'')

    t1 = threading.Thread(target=read_stream, args=(proc.stdout, stdout_q), daemon=True)
    t2 = threading.Thread(target=read_stream, args=(proc.stderr, stderr_q), daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=timeout)
    t2.join(timeout=timeout)

    if t1.is_alive() or t2.is_alive():
        _kill_process_tree(proc)
        raise subprocess.TimeoutExpired(cmd='', timeout=timeout)

    proc.wait()
    return stdout_q.get_nowait(), stderr_q.get_nowait()


def _kill_process_tree(proc: subprocess.Popen) -> None:
    try:
        if sys.platform == 'win32':
            subprocess.run(
                ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass


def _smart_decode(raw: bytes) -> str:
    if not raw:
        return ''
    for enc in ('utf-8', 'utf-16', 'gbk', 'latin-1'):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return raw.decode('utf-8', errors='replace')
