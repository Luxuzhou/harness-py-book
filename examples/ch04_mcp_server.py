"""第4章 MCP Server 最小示例。

这是一个教学用 stdio JSON-RPC 服务，演示 initialize、tools/list 与
tools/call 三个最小闭环。示例直接放在 examples/ 下，和当前章节入口保持一致。
"""

from __future__ import annotations

import json
import sys
from typing import Any


NOTES: list[dict[str, str]] = [
    {"title": "Agent架构", "content": "Model + Harness"},
    {"title": "MCP协议", "content": "resources / prompts / tools"},
]


TOOLS = [
    {
        "name": "list_notes",
        "description": "列出所有笔记",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "default": 5},
            },
        },
    },
    {
        "name": "add_note",
        "description": "添加一条笔记",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
]


def _text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "list_notes":
        limit = int(args.get("limit", 5))
        lines = [
            f"#{idx} {note['title']}: {note['content']}"
            for idx, note in enumerate(NOTES[:limit], 1)
        ]
        return _text_result("\n".join(lines))

    if name == "add_note":
        title = str(args.get("title", "")).strip()
        content = str(args.get("content", "")).strip()
        if not title or not content:
            raise ValueError("title and content are required")
        NOTES.append({"title": title, "content": content})
        return _text_result(f"已添加笔记: {title}")

    raise ValueError(f"unknown tool: {name}")


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    try:
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "ch04-notes-server", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            result = _call_tool(
                str(params.get("name", "")),
                params.get("arguments") or {},
            )
        else:
            raise ValueError(f"unknown method: {method}")

        return {"jsonrpc": "2.0", "id": req_id, "result": result}
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32000, "message": str(exc)},
        }


def serve() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        response = handle_request(json.loads(line))
        print(json.dumps(response, ensure_ascii=False), flush=True)


def run_self_test() -> None:
    init = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert "result" in init and "tools" in init["result"]["capabilities"]

    listed = handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert len(listed["result"]["tools"]) == 2

    added = handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "add_note",
            "arguments": {"title": "压缩策略", "content": "四级压缩"},
        },
    })
    assert "已添加笔记" in added["result"]["content"][0]["text"]

    notes = handle_request({
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {"name": "list_notes", "arguments": {"limit": 5}},
    })
    assert "压缩策略" in notes["result"]["content"][0]["text"]
    print("MCP Server self-test passed")


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_self_test()
    else:
        serve()
