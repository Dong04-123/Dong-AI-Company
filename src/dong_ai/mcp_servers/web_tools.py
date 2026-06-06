#!/usr/bin/env python3
"""
Dong AI — Web Tools MCP Server

标准化上网工具集，零 API Key 需求。
使用官方的 MCP Python SDK，可被任何 MCP 客户端连接。

内置两个工具:
  - web_search(query, max_results=5)  — DuckDuckGo 搜索
  - web_fetch(url, max_length=5000)   — URL 内容抓取

作为 MCP 服务器运行:
  python3 -m dong_ai.mcp_servers.web_tools

添加到 Dong AI:
  dong plugin install dong-web-tools

直接测试:
  python3 -m dong_ai.mcp_servers.web_tools --test-search "今天天气"
"""

import json, sys, urllib.request, urllib.parse, urllib.error, re, html, os
from typing import Any

try:
    from mcp.server import Server, NotificationOptions
    from mcp.server.models import InitializationOptions
    from mcp.types import (
        GetPromptResult,
        Prompt,
        PromptArgument,
        PromptMessage,
        TextContent,
        Tool,
        TextResourceContents,
        ListResourcesResult,
        ListPromptsResult,
        ListToolsResult,
        ReadResourceResult,
        CallToolResult,
    )
    import anyio
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


# ═══════════════════════════════════════════════════════════
# 标准工具函数
# ═══════════════════════════════════════════════════════════

def ddgs_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo 搜索（纯 urllib，零依赖）"""
    url = "https://html.duckduckgo.com/html/"
    data = urllib.parse.urlencode({"q": query}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_content = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return [{"title": f"搜索失败: {e}", "url": "", "snippet": ""}]

    results = []
    for match in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html_content, re.DOTALL
    ):
        url_raw = match.group(1)
        title = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        snippet = re.sub(r'<[^>]+>', '', match.group(3)).strip()
        if url_raw.startswith("//"):
            url_raw = "https:" + url_raw
        results.append({
            "title": html.unescape(title),
            "url": html.unescape(url_raw),
            "snippet": html.unescape(snippet),
        })
        if len(results) >= max_results:
            break
    return results if results else [{"title": "无结果", "url": "", "snippet": ""}]


def fetch_url(url: str, max_length: int = 5000) -> dict:
    """获取 URL 内容并提取可读文本"""
    if not url.startswith(("http://", "https://")):
        return {"error": "URL must start with http:// or https://", "content": ""}
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
            if "charset=" in content_type:
                charset = content_type.split("charset=")[-1].split(";")[0].strip()
            else:
                charset = "utf-8"
            try:
                text = raw.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                text = raw.decode("utf-8", errors="replace")
            text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            text = html.unescape(text)
            if len(text) > max_length:
                text = text[:max_length] + "..."
            return {"content": text, "url": url, "content_type": content_type}
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}", "content": ""}
    except urllib.error.URLError as e:
        return {"error": f"Connection failed: {e.reason}", "content": ""}
    except Exception as e:
        return {"error": str(e), "content": ""}


# ═══════════════════════════════════════════════════════════
# SDK 模式
# ═══════════════════════════════════════════════════════════

async def _run_sdk():
    """使用官方 MCP SDK 运行"""
    server = Server("dong-web-tools")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="web_search",
                description="通过 DuckDuckGo 搜索互联网，无需任何 API Key。支持中文和英文搜索，返回标题、URL 和摘要。适合查找最新新闻、资料、文档。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"},
                        "max_results": {"type": "number", "description": "返回结果数（1-10）", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="web_fetch",
                description="获取指定 URL 的网页内容并提取可读文本。自动去除 HTML 标签、Script 和 Style。支持任何公开网页。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "网页 URL（必须以 http:// 或 https:// 开头）"},
                        "max_length": {"type": "number", "description": "最大返回字符数", "default": 5000},
                    },
                    "required": ["url"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        if name == "web_search":
            query = arguments.get("query", "")
            max_results = min(int(arguments.get("max_results", 5)), 10)
            if not query:
                return CallToolResult(isError=True, content=[TextContent(type="text", text="query is required")])
            results = ddgs_search(query, max_results)
            text_parts = []
            for i, r in enumerate(results, 1):
                text_parts.append(f"{i}. {r['title']}")
                if r.get('snippet'):
                    text_parts.append(f"   {r['snippet'][:300]}")
                if r.get('url'):
                    text_parts.append(f"   来源: {r['url']}")
            return CallToolResult(content=[TextContent(type="text", text="\n".join(text_parts))])

        if name == "web_fetch":
            url = arguments.get("url", "")
            max_length = int(arguments.get("max_length", 5000))
            if not url:
                return CallToolResult(isError=True, content=[TextContent(type="text", text="url is required")])
            result = fetch_url(url, max_length)
            if result.get("error"):
                return CallToolResult(isError=True, content=[TextContent(type="text", text=f"错误: {result['error']}")])
            return CallToolResult(content=[TextContent(type="text", text=result["content"])])

        return CallToolResult(isError=True, content=[TextContent(type="text", text=f"Unknown tool: {name}")])

    await server.run(
        sys.stdin,
        sys.stdout,
        InitializationOptions(
            server_name="dong-web-tools",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        ),
    )


# ═══════════════════════════════════════════════════════════
# Fallback: 手写 JSON-RPC 模式（无 SDK）
# ═══════════════════════════════════════════════════════════

_request_id = 0


def _jsonrpc(method: str, params: dict = None) -> dict:
    global _request_id
    _request_id += 1
    return {"jsonrpc": "2.0", "id": _request_id, "method": method, "params": params or {}}


def _send(msg: dict):
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _read() -> dict | None:
    line = sys.stdin.readline()
    if not line:
        return None
    try:
        return json.loads(line.strip())
    except json.JSONDecodeError:
        return None


def _result(req: dict, data):
    return {"jsonrpc": "2.0", "id": req.get("id"), "result": data}


def _error(req: dict, code: int, message: str, data=None):
    err = {"code": code, "message": message}
    if data:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req.get("id"), "error": err}


def _handle_request(req: dict) -> dict | None:
    method = req.get("method", "")
    params = req.get("params", {})

    if method == "initialize":
        return _result(req, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "dong-web-tools", "version": "0.1.0"},
        })
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return _result(req, {
            "tools": [
                {
                    "name": "web_search",
                    "description": "DuckDuckGo 搜索互联网，无需 API Key。支持中英文，返回标题/URL/摘要。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                            "max_results": {"type": "number", "description": "返回结果数（1-10）", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "web_fetch",
                    "description": "获取 URL 网页内容并提取可读文本。自动去 HTML/Script/Style。",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "网页 URL（http:// 或 https:// 开头）"},
                            "max_length": {"type": "number", "description": "最大返回字符数", "default": 5000},
                        },
                        "required": ["url"],
                    },
                },
            ]
        })
    if method == "tools/call":
        tool = params.get("name", "")
        args = params.get("arguments", {})
        if tool == "web_search":
            query = args.get("query", "")
            max_results = min(int(args.get("max_results", 5)), 10)
            if not query:
                return _error(req, -32000, "query is required")
            results = ddgs_search(query, max_results)
            text_parts = []
            for i, r in enumerate(results, 1):
                text_parts.append(f"{i}. {r['title']}")
                if r.get('snippet'):
                    text_parts.append(f"   {r['snippet'][:300]}")
                if r.get('url'):
                    text_parts.append(f"   来源: {r['url']}")
            return _result(req, {"content": [{"type": "text", "text": "\n".join(text_parts)}], "isError": False})
        if tool == "web_fetch":
            url = args.get("url", "")
            max_length = int(args.get("max_length", 5000))
            if not url:
                return _error(req, -32000, "url is required")
            result = fetch_url(url, max_length)
            if result.get("error"):
                return _result(req, {"content": [{"type": "text", "text": f"错误: {result['error']}"}], "isError": True})
            return _result(req, {"content": [{"type": "text", "text": result["content"]}], "isError": False})
        return _error(req, -32601, f"Unknown tool: {tool}")
    if method.startswith("notifications/"):
        return None
    return _error(req, -32601, f"Method not found: {method}")


def _run_fallback():
    """手写 JSON-RPC 模式主循环"""
    while True:
        req = _read()
        if req is None:
            break
        try:
            resp = _handle_request(req)
            if resp is not None:
                _send(resp)
        except Exception as e:
            _send(_error(req, -32603, f"Internal error: {e}"))


# ═══════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════

def main():
    # 测试模式
    if "--test-search" in sys.argv:
        idx = sys.argv.index("--test-search")
        query = " ".join(sys.argv[idx + 1:]) if idx + 1 < len(sys.argv) else "test"
        print(f"Search: {query}\n{'='*50}")
        for r in ddgs_search(query):
            print(f"  {r['title']}\n  {r['snippet'][:200]}\n  {r['url']}\n")
        return

    if "--test-fetch" in sys.argv:
        idx = sys.argv.index("--test-fetch")
        url = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "https://example.com"
        print(f"Fetch: {url}\n{'='*50}")
        result = fetch_url(url)
        if result.get("error"):
            print(f"Error: {result['error']}")
        else:
            print(result["content"][:1000])
        return

    # 正常 MCP 服务器模式
    _run_fallback()


if __name__ == "__main__":
    main()
