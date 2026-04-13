"""
MCP客户端
=========
连接MCP Server，发现并调用外部工具。
支持stdio传输，JSON-RPC 2.0协议。
对标OpenHarness的mcp/client.py。

设计：
- 通过subprocess启动Server子进程
- 用stdin/stdout进行JSON-RPC通信
- McpClientManager管理多个Server连接
- 纯标准库实现
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ============ 数据结构 ============

@dataclass
class McpServerConfig:
    """MCP Server配置。"""
    name: str
    command: str            # 启动命令，如 'python mcp_server.py'
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ''           # 工作目录


@dataclass
class McpTool:
    """从MCP Server发现的工具。"""
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str        # 来自哪个Server


# ============ JSON-RPC辅助 ============

class _JsonRpcError(Exception):
    """JSON-RPC错误。"""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f'JSON-RPC error {code}: {message}')


def _make_request(method: str, params: dict | None = None, req_id: int = 1) -> bytes:
    """构造JSON-RPC 2.0请求。"""
    msg: dict[str, Any] = {
        'jsonrpc': '2.0',
        'id': req_id,
        'method': method,
    }
    if params is not None:
        msg['params'] = params
    return (json.dumps(msg) + '\n').encode('utf-8')


def _parse_response(line: str) -> dict[str, Any]:
    """解析JSON-RPC 2.0响应。"""
    data = json.loads(line)
    if 'error' in data and data['error']:
        err = data['error']
        raise _JsonRpcError(
            code=err.get('code', -1),
            message=err.get('message', 'Unknown error'),
            data=err.get('data'),
        )
    return data


# ============ McpClient ============

class McpClient:
    """
    单个MCP Server的客户端连接。

    通过stdio传输与Server通信：

    1. 启动Server子进程
    2. 发送initialize请求
    3. 调用tools/list发现工具
    4. 调用tools/call执行工具
    """

    PROTOCOL_VERSION = '2024-11-05'

    def __init__(self, config: McpServerConfig):
        self.config = config
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._req_id = 0
        self._tools: list[McpTool] = []
        self._connected = False
        self._reader_thread: threading.Thread | None = None
        self._responses: dict[int, dict] = {}
        self._response_events: dict[int, threading.Event] = {}

    @property
    def connected(self) -> bool:
        """是否已连接。"""
        return self._connected and self._process is not None and self._process.poll() is None

    def connect(self, timeout: float = 10.0) -> bool:
        """
        启动Server并完成初始化握手。

        Args:
            timeout: 握手超时秒数

        Returns:
            是否成功
        """
        if self.connected:
            return True

        # 构建启动命令
        cmd = [self.config.command] + self.config.args
        env = {**os.environ, **self.config.env} if self.config.env else None
        cwd = self.config.cwd or None

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=cwd,
                bufsize=0,
            )
        except (FileNotFoundError, OSError) as exc:
            return False

        # 启动读取线程
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name=f'mcp-reader-{self.config.name}',
        )
        self._reader_thread.start()

        # 发送initialize
        try:
            resp = self._send_request('initialize', {
                'protocolVersion': self.PROTOCOL_VERSION,
                'capabilities': {},
                'clientInfo': {
                    'name': 'harness-py-pro',
                    'version': '0.2.0',
                },
            }, timeout=timeout)
        except (TimeoutError, _JsonRpcError, Exception):
            self.disconnect()
            return False

        # 发送initialized通知（无id，不需要响应）
        self._send_notification('notifications/initialized', {})

        self._connected = True
        return True

    def list_tools(self) -> list[McpTool]:
        """
        发现Server提供的工具。

        Returns:
            工具列表

        Raises:
            RuntimeError: 未连接
        """
        self._ensure_connected()

        resp = self._send_request('tools/list', {})
        result = resp.get('result', {})
        tools_data = result.get('tools', [])

        self._tools = []
        for t in tools_data:
            tool = McpTool(
                name=t.get('name', ''),
                description=t.get('description', ''),
                input_schema=t.get('inputSchema', {}),
                server_name=self.config.name,
            )
            self._tools.append(tool)

        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any], timeout: float = 30.0) -> str:
        """
        调用工具，返回结果文本。

        Args:
            name: 工具名称
            arguments: 工具参数
            timeout: 调用超时秒数

        Returns:
            工具执行结果文本

        Raises:
            RuntimeError: 未连接或工具调用失败
        """
        self._ensure_connected()

        resp = self._send_request('tools/call', {
            'name': name,
            'arguments': arguments,
        }, timeout=timeout)

        result = resp.get('result', {})
        content_list = result.get('content', [])

        # 拼接所有text类型的内容
        texts = []
        for item in content_list:
            if isinstance(item, dict) and item.get('type') == 'text':
                texts.append(item.get('text', ''))

        return '\n'.join(texts) if texts else json.dumps(result)

    def disconnect(self):
        """关闭连接，终止Server子进程。"""
        self._connected = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    # ---- 内部方法 ----

    def _ensure_connected(self):
        """确保已连接。"""
        if not self.connected:
            raise RuntimeError(f'Not connected to MCP server: {self.config.name}')

    def _next_id(self) -> int:
        """获取下一个请求ID。"""
        with self._lock:
            self._req_id += 1
            return self._req_id

    def _send_request(
        self,
        method: str,
        params: dict | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """发送请求并等待响应。"""
        req_id = self._next_id()
        event = threading.Event()

        with self._lock:
            self._response_events[req_id] = event

        data = _make_request(method, params, req_id)
        try:
            self._process.stdin.write(data)  # type: ignore[union-attr]
            self._process.stdin.flush()  # type: ignore[union-attr]
        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(f'Failed to send to MCP server: {exc}')

        if not event.wait(timeout=timeout):
            raise TimeoutError(f'MCP request timeout: {method} (id={req_id})')

        with self._lock:
            resp = self._responses.pop(req_id, {})
            self._response_events.pop(req_id, None)

        if 'error' in resp and resp['error']:
            err = resp['error']
            raise _JsonRpcError(
                code=err.get('code', -1),
                message=err.get('message', 'Unknown'),
            )

        return resp

    def _send_notification(self, method: str, params: dict | None = None):
        """发送通知（不需要响应）。"""
        msg: dict[str, Any] = {
            'jsonrpc': '2.0',
            'method': method,
        }
        if params is not None:
            msg['params'] = params
        data = (json.dumps(msg) + '\n').encode('utf-8')
        try:
            self._process.stdin.write(data)  # type: ignore[union-attr]
            self._process.stdin.flush()  # type: ignore[union-attr]
        except (BrokenPipeError, OSError):
            pass

    def _read_loop(self):
        """后台线程：持续读取Server stdout。"""
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        for raw_line in proc.stdout:
            line = raw_line.decode('utf-8', errors='replace').strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            req_id = data.get('id')
            if req_id is not None:
                with self._lock:
                    self._responses[req_id] = data
                    event = self._response_events.get(req_id)
                    if event:
                        event.set()


# ============ McpClientManager ============

class McpClientManager:
    """
    管理多个MCP Server连接。

    用法::

        manager = McpClientManager()
        manager.add_server(McpServerConfig(name='db', command='python db_server.py'))
        manager.connect_all()
        tools = manager.all_tools()
        result = manager.call('db.query', {'sql': 'SELECT ...'})
        manager.disconnect_all()

    工具名称约定：<server_name>.<tool_name>，如 'db.query'。
    """

    def __init__(self):
        self._clients: dict[str, McpClient] = {}
        self._tool_map: dict[str, tuple[McpClient, McpTool]] = {}

    def add_server(self, config: McpServerConfig):
        """
        注册一个MCP Server配置。

        Args:
            config: Server配置
        """
        self._clients[config.name] = McpClient(config)

    def connect_all(self, timeout: float = 10.0) -> dict[str, bool]:
        """
        连接所有已注册的Server。

        Args:
            timeout: 每个Server的连接超时

        Returns:
            {server_name: success} 字典
        """
        results: dict[str, bool] = {}
        for name, client in self._clients.items():
            ok = client.connect(timeout=timeout)
            results[name] = ok
            if ok:
                # 自动发现工具
                try:
                    tools = client.list_tools()
                    for tool in tools:
                        qualified = f'{name}.{tool.name}'
                        self._tool_map[qualified] = (client, tool)
                except Exception:
                    pass
        return results

    def all_tools(self) -> list[McpTool]:
        """
        获取所有Server的工具列表。

        Returns:
            全部工具（合并去重）
        """
        return [tool for _, tool in self._tool_map.values()]

    def all_tool_schemas(self) -> list[dict[str, Any]]:
        """
        获取所有工具的JSON Schema（可注入到engine的tool列表）。

        Returns:
            工具schema列表，每项包含 name/description/parameters
        """
        schemas: list[dict[str, Any]] = []
        for qualified_name, (client, tool) in self._tool_map.items():
            schemas.append({
                'name': qualified_name,
                'description': tool.description,
                'parameters': tool.input_schema,
            })
        return schemas

    def call(self, tool_name: str, arguments: dict[str, Any], timeout: float = 30.0) -> str:
        """
        调用工具（自动路由到正确的Server）。

        Args:
            tool_name: 完整工具名（如 'db.query'）或短名称
            arguments: 工具参数
            timeout: 超时秒数

        Returns:
            工具执行结果文本

        Raises:
            ValueError: 工具未找到
        """
        # 精确匹配
        entry = self._tool_map.get(tool_name)

        # 尝试短名称匹配
        if entry is None:
            candidates = [
                (k, v) for k, v in self._tool_map.items()
                if k.endswith(f'.{tool_name}')
            ]
            if len(candidates) == 1:
                entry = candidates[0][1]
            elif len(candidates) > 1:
                names = [c[0] for c in candidates]
                raise ValueError(f'Ambiguous tool name "{tool_name}": {names}')

        if entry is None:
            raise ValueError(f'Tool not found: {tool_name}')

        client, tool = entry
        # 用原始工具名（不含server前缀）调用
        return client.call_tool(tool.name, arguments, timeout=timeout)

    def disconnect_all(self):
        """断开所有Server连接。"""
        for client in self._clients.values():
            try:
                client.disconnect()
            except Exception:
                pass
        self._tool_map.clear()

    def server_status(self) -> dict[str, bool]:
        """
        获取所有Server的连接状态。

        Returns:
            {server_name: connected} 字典
        """
        return {name: client.connected for name, client in self._clients.items()}
