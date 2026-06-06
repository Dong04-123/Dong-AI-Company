"""
Dong AI — 工具执行器

统一管理所有 [TOOL_CALL:xxx] 的解析和执行。
消除 tui.py 和 worker.py 之间的工具调用代码重复。
"""
from __future__ import annotations

import os, re, time, subprocess, json
from pathlib import Path


class ToolExecutor:
    """工具执行器——解析 [TOOL_CALL:name] 并执行"""

    def __init__(self, ceo_mem=None, model_pool=None) -> None:
        self.ceo_mem = ceo_mem
        self.model_pool = model_pool
        self.state = {}

    def parse(self, text: str) -> list:
        """解析文本中的 [TOOL_CALL:xxx] 调用，返回 [(name, params), ...]"""
        results = []
        for match in re.finditer(r'\[TOOL_CALL:\s*(\w+)\](.*?)\[/TOOL_CALL\]', text, re.DOTALL):
            name = match.group(1)
            body = match.group(2).strip()
            params = {}
            for line in body.split('\n'):
                line = line.strip()
                if '=' in line:
                    k, v = line.split('=', 1)
                    params[k.strip()] = v.strip()
            results.append((name, params))
        return results

    def execute(self, name: str, params: dict) -> str:
        """执行单个工具调用，返回结果文本"""
        handler = getattr(self, f"do_{name}", None)
        if handler:
            try:
                return handler(**params)
            except Exception as e:
                return f"❌ 工具 {name} 执行失败: {e}"
        return f"❌ 未知工具: {name}"

    def execute_all(self, text: str, max_turns: int = 3) -> list:
        """解析并执行文本中的所有工具调用，返回 [(name, result), ...]"""
        results = []
        calls = self.parse(text)
        for name, params in calls[:max_turns]:
            result = self.execute(name, params)
            results.append((name, params, result))
        return results

    # ── 内置工具 ──

    def do_web_search(self, query="", q="") -> str:
        q = query or q
        if not q: return "请输入搜索词"
        from .web_search import search_formatted
        r = search_formatted(q, 5)
        return r or "搜索无结果"

    def do_web_fetch(self, url="") -> str:
        """抓取网页内容（Agent 原生能力，零外部依赖）"""
        if not url: return "请指定 url"
        from .mcp_servers.web_tools import fetch_url
        result = fetch_url(url, max_length=8000)
        if result.get("error"):
            return f"❌ 抓取失败: {result['error']}"
        text = result["content"]
        return f"📄 {url}\n{'='*40}\n{text[:5000]}" + ("\n...（截断）" if len(text) > 5000 else "")

    def do_write_file(self, path="", content="") -> str:
        if not path: return "请指定 path"
        fp = Path(path).expanduser()
        if not fp.is_absolute(): fp = Path.home() / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding='utf-8')
        return f"✅ 已写入 {fp} ({len(content)} 字节)"

    def do_read_file(self, path="") -> str:
        if not path: return "请指定 path"
        fp = Path(path).expanduser()
        if not fp.is_absolute(): fp = Path.home() / path
        if not fp.exists(): return f"❌ 文件不存在: {fp}"
        text = fp.read_text(encoding='utf-8', errors='replace')
        return f"📄 {fp} ({len(text)} 字符):\n{text[:3000]}"

    def do_list_files(self, path=".") -> str:
        fp = Path(path).expanduser()
        if not fp.is_absolute(): fp = Path.home() / path
        if not fp.is_dir(): return f"❌ 目录不存在: {fp}"
        items = []
        for f in fp.iterdir():
            tag = "📄" if f.is_file() else "📁"
            size = f.stat().st_size if f.is_file() else 0
            items.append(f"{tag} {f.name} ({size:,} 字节)" if f.is_file() else f"{tag} {f.name}/")
        result = "\n".join(items[:30])
        if len(items) > 30: result += f"\n... 共 {len(items)} 项"
        return result

    def do_run(self, cmd="", command="") -> str:
        c = cmd or command
        if not c: return "请指定 cmd"
        try:
            r = subprocess.run(c, shell=True, capture_output=True, text=True, timeout=30)
            out = (r.stdout or "")[:2000]
            err = (r.stderr or "")[:500]
            return out + ("\n⚠ " + err if err else "")
        except subprocess.TimeoutExpired:
            return "⏱ 命令超时(30s)"

    def do_browser_navigate(self, url="") -> str:
        if not url: return "请指定 url"
        from .browser_tool import navigate
        return navigate(url)

    def do_browser_screenshot(self, url="") -> str:
        if not url: return "请指定 url"
        from .browser_tool import screenshot
        return screenshot(url)

    def do_memory(self, action="", target="memory", content="", key="") -> str:
        if not self.ceo_mem: return "记忆系统未初始化"
        if action == "add" and content:
            key = key or f"fact_{int(time.time())}"
            self.ceo_mem.set(key, content, category=target, source='agent')
            return f"已记住: {key}"
        elif action == "get" and key:
            val = self.ceo_mem.get(key)
            return f"{key}: {val}" if val else "未找到"
        elif action == "replace" and key and content:
            self.ceo_mem.set(key, content, category=target, source='agent')
            return f"已更新: {key}"
        elif action == "remove" and key:
            self.ceo_mem.delete(key)
            return f"已删除: {key}"
        elif action == "list":
            facts = self.ceo_mem.facts(target if target != 'memory' else '')
            return "\n".join(f"[{f['category']}] {f['key']}: {f['value'][:100]}" for f in facts[:10]) or "空"
        return "可用操作: add/get/replace/remove/list"

    def do_memory_query(self, query="", key="") -> str:
        if not self.ceo_mem: return "记忆系统未初始化"
        q = query or key
        results = self.ceo_mem.query(q, 5)
        if results:
            return "\n".join(f"[{r['source']}] {r['key']}: {r['value'][:200]}" for r in results)
        return "未找到"

    def do_graph_query(self, query=""):
        if not query: return "请指定 query"
        from .datastore import get_repo
        repo = get_repo("project")
        results = repo.query(query)
        if results:
            return "\n".join(f"[{r['source']}] {r['key']}: {r['value'][:200]}" for r in results)
        return "未找到"

    def do_column_status(self, project_type=""):
        """查看 Column Memory 状态 — 各列加载情况、token 用量"""
        from .column_memory import ColumnMemory
        cm = ColumnMemory(project_id=project_type or "current")
        return cm.cmd_status()
