"""Dong AI — MCP 客户端

通过 stdio JSON-RPC 调用 MCP 服务器工具。
集成到 WorkerPool 的 ReAct 工具循环中。"""

from __future__ import annotations

import json, subprocess, os, sys, time
from pathlib import Path
from typing import Optional


class MCPClient:
    """MCP 协议客户端 — stdio 传输"""

    def __init__(self, server_name: str, command: str, args: list = None) -> None:
        self.server_name = server_name
        self.command = command
        self.args = args or []
        self._process: Optional[subprocess.Popen] = None
        self._request_id = 0
        self._tools_cache = None

    def connect(self) -> bool:
        """启动 MCP 服务器进程并初始化"""
        if self._process:
            return True
        try:
            self._process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            # 发送 initialize
            resp = self._request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "dong-ai", "version": "0.1.0"},
            })
            return resp is not None
        except Exception as e:
            print(f"  [MCP] {self.server_name} 连接失败: {e}")
            self._process = None
            return False

    def disconnect(self) -> None:
        """关闭 MCP 服务器"""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except:
                self._process.kill()
            self._process = None

    def list_tools(self) -> list:
        """获取服务器提供的工具列表"""
        if self._tools_cache is not None:
            return self._tools_cache
        resp = self._request("tools/list", {})
        if resp and "result" in resp:
            tools = resp["result"].get("tools", [])
            self._tools_cache = tools
            return tools
        return []

    def call_tool(self, name: str, arguments: dict = None) -> dict:
        """调用 MCP 工具"""
        resp = self._request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })
        if resp and "result" in resp:
            result = resp["result"]
            content = result.get("content", [])
            # 合并文本内容
            texts = []
            for c in content:
                if c.get("type") == "text":
                    texts.append(c.get("text", ""))
            return {"content": "\n".join(texts), "isError": result.get("isError", False)}
        return {"content": f"<MCP_ERROR: {resp}>", "isError": True}

    def _request(self, method: str, params: dict) -> dict:
        """发送 JSON-RPC 请求并等待响应"""
        if not self._process:
            return None
        self._request_id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        req_bytes = (json.dumps(req) + "\n").encode()
        try:
            self._process.stdin.write((json.dumps(req) + "\n"))
            self._process.stdin.flush()
            # 读取响应（一行 JSON）
            line = self._process.stdout.readline()
            if line:
                return json.loads(line)
        except Exception as e:
            print(f"  [MCP] 请求失败 {method}: {e}")
        return None

    def __enter__(self) -> MCPClient:
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.disconnect()


# ── 发现可用的 MCP 服务器 ──

def discover_mcp_servers() -> list:
    """扫描配置文件，返回所有 MCP 服务器配置"""
    servers = []

    # JSON 配置
    for cfg_path in [
        Path.home() / ".cursor" / "mcp.json",
        Path.cwd() / ".mcp.json",
    ]:
        if not cfg_path.exists():
            continue
        try:
            data = json.loads(cfg_path.read_text())
            for name, cfg in data.get("mcpServers", data.get("servers", {})).items():
                if isinstance(cfg, dict) and cfg.get("command"):
                    servers.append({
                        "name": name,
                        "command": cfg["command"],
                        "args": cfg.get("args", []),
                        "source": str(cfg_path),
                    })
        except Exception:
            pass

    # Hermes config.yaml
    hermes_cfg = Path.home() / ".hermes" / "config.yaml"
    if hermes_cfg.exists():
        try:
            import re
            text = hermes_cfg.read_text()
            in_mcp_servers = False
            current_name = None
            for line in text.split("\n"):
                if re.match(r'^\s+servers:', line):
                    in_mcp_servers = True
                    continue
                if in_mcp_servers:
                    m = re.match(r'^\s{4}(\w[\w-]*):', line)
                    if m:
                        current_name = m.group(1)
                        continue
                    if current_name and re.match(r'^\s{6}command:', line):
                        cmd = line.split(":", 1)[1].strip().strip('"\'')
                        servers.append({
                            "name": current_name,
                            "command": cmd,
                            "args": [],
                            "source": str(hermes_cfg),
                        })
                        current_name = None
                    elif not line.startswith(" "):
                        break
        except Exception:
            pass

    return servers


def format_mcp_tools_for_prompt(servers: list) -> str:
    """把 MCP 工具格式化成 LLM 可读的工具列表"""
    parts = []
    for srv in servers:
        parts.append(f"MCP 服务器: {srv['name']}")
        parts.append(f"  命令: {srv['command']} {' '.join(srv.get('args',[]))}")
        parts.append(f"  来源: {srv.get('source', '')}")
    return "\n".join(parts)
