"""
Dong AI — 插件注册表系统

职责: 管理插件市场、安装/卸载、MCP 工具注册

插件 = 一组 MCP 服务器配置 + 元数据
注册表 = known_plugins.json（内置）+ 用户自定义

用法:
  dong plugin list           → 列出已安装插件
  dong plugin search         → 搜索注册表
  dong plugin install <name> → 安装插件（写入 .mcp.json）
  dong plugin remove  <name> → 卸载插件
"""
from __future__ import annotations

import json, os, shutil, subprocess, sys
from pathlib import Path
from typing import Optional

# ── 内置注册表 ──
# 社区贡献的可安装插件
KNOWN_PLUGINS = {
    # === Dong AI 官方内置 ===
    "dong-web-tools": {
        "name": "上网工具（官方）",
        "description": "Dong AI 官方上网工具集。搜索互联网 (DuckDuckGo) + 网页内容抓取。零 API Key，零外部依赖，内置在 dong-ai 中。",
        "command": "python3",
        "args": ["-m", "dong_ai.mcp_servers.web_tools"],
        "url": "https://github.com/Dong04-123/Dong-AI-Company",
        "tags": ["web", "search", "fetch", "official"],
        "builtin": True,
    },
    # === 社区插件 ===
    "filesystem": {
        "name": "文件系统",
        "description": "安全的文件读写、搜索、元数据查询。npm 包名 @modelcontextprotocol/server-filesystem，由 modelcontextprotocol 官方维护。",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", os.getcwd()],
        "url": "https://github.com/modelcontextprotocol/servers",
        "tags": ["file", "fs", "io"],
    },
    "github": {
        "name": "GitHub",
        "description": "仓库管理、Issue/PR CRUD、代码搜索、文件操作。npm 包名 @modelcontextprotocol/server-github，需要 GITHUB_TOKEN 环境变量。",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {"GITHUB_TOKEN": ""},
        "url": "https://github.com/modelcontextprotocol/servers",
        "tags": ["git", "github", "devops"],
    },
    "puppeteer": {
        "name": "浏览器自动化",
        "description": "Puppeteer 驱动的浏览器操作：截图、点击、填写表单、获取网页内容。npm 包名 @modelcontextprotocol/server-puppeteer。首次运行会自动下载 Chromium（~300MB），请耐心等待。",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-puppeteer"],
        "url": "https://github.com/modelcontextprotocol/servers",
        "tags": ["browser", "automation", "test", "web"],
    },
    "web-search": {
        "name": "Brave 搜索",
        "description": "通过 Brave Search API 进行网页和新闻搜索。npm 包名 @modelcontextprotocol/server-brave-search。需要免费注册 Brave Search API 获取 API Key: https://brave.com/search/api/",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": ""},
        "url": "https://github.com/modelcontextprotocol/servers",
        "tags": ["search", "web", "news"],
    },
    "memory": {
        "name": "记忆系统",
        "description": "基于知识图谱的持久化记忆（实体、关系、时间线）。npm 包名 @modelcontextprotocol/server-memory。",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-memory"],
        "url": "https://github.com/modelcontextprotocol/servers",
        "tags": ["memory", "knowledge", "graph"],
    },
    "sequential-thinking": {
        "name": "链式思考",
        "description": "结构化多步推理，逐步推导复杂问题",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "url": "https://github.com/modelcontextprotocol/servers",
        "tags": ["reasoning", "thinking", "analysis"],
    },
}


def _mcp_config_path() -> Path:
    """MCP 配置文件路径（通用 .mcp.json）"""
    return Path.cwd() / ".mcp.json"


def _dong_plugin_dir() -> Path:
    """Dong AI 插件数据目录"""
    d = Path.home() / ".dong" / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_plugins() -> list[dict]:
    """列出当前安装/发现的插件"""
    plugins = []
    config_path = _mcp_config_path()
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
            servers = data.get("mcpServers", data.get("servers", {}))
            for name, cfg in servers.items():
                if isinstance(cfg, dict) and cfg.get("command"):
                    plugins.append({
                        "name": name,
                        "status": "installed",
                        "command": cfg["command"],
                        "args": cfg.get("args", []),
                        "env": cfg.get("env", {}),
                    })
        except (json.JSONDecodeError, OSError):
            pass

    # 内置插件（始终可用，不管是否安装）
    for name, info in KNOWN_PLUGINS.items():
        if info.get("builtin") and not any(p["name"] == name for p in plugins):
            plugins.append({
                "name": name,
                "status": "builtin",
                "command": info["command"],
                "args": info["args"],
                "env": info.get("env", {}),
            })

    return plugins


def search_registry(query: str = "") -> list[dict]:
    """在注册表中搜索可安装的插件"""
    results = []
    q = query.lower()
    for name, info in KNOWN_PLUGINS.items():
        if not q or q in name or q in info["description"].lower() or any(q in t for t in info.get("tags", [])):
            results.append({"id": name, **info})
    return results


def install_plugin(plugin_id: str, env_overrides: Optional[dict] = None) -> bool:
    """安装插件到 .mcp.json"""
    if plugin_id not in KNOWN_PLUGINS:
        print(f"  ✗ 未知插件: {plugin_id}")
        print(f"    可用: {', '.join(KNOWN_PLUGINS.keys())}")
        return False

    info = KNOWN_PLUGINS[plugin_id]
    config_path = _mcp_config_path()

    # 读取或创建配置
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    else:
        data = {}

    servers = data.get("mcpServers", data.get("servers", {}))
    if plugin_id in servers:
        print(f"  ⚠️ 插件 {plugin_id} 已安装，跳过")
        return True

    # 构建 MCP 服务器配置
    server_cfg = {
        "command": info["command"],
        "args": info["args"],
    }
    if info.get("env"):
        env = dict(info["env"])
        if env_overrides:
            env.update(env_overrides)
        server_cfg["env"] = env

    servers[plugin_id] = server_cfg
    if "servers" in data:
        data["servers"] = servers
    else:
        data["mcpServers"] = servers

    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ 插件 {plugin_id} 已安装 → {config_path}")
    print(f"     命令: {info['command']} {' '.join(info['args'][:3])}...")
    return True


def remove_plugin(plugin_id: str) -> bool:
    """从 .mcp.json 卸载插件"""
    config_path = _mcp_config_path()
    if not config_path.exists():
        print(f"  ✗ 未找到 MCP 配置")
        return False

    data = json.loads(config_path.read_text())
    servers = data.get("mcpServers", data.get("servers", {}))
    if plugin_id not in servers:
        print(f"  ✗ 插件 {plugin_id} 未安装")
        return False

    del servers[plugin_id]
    if "servers" in data:
        data["servers"] = servers
    else:
        data["mcpServers"] = servers

    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅ 插件 {plugin_id} 已卸载")
    return True
