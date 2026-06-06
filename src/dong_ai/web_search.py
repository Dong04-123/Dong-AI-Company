"""
全网检索模块 v2 — 使用 ddgs 库（DuckDuckGo 官方 API）

比 v1（HTML 解析）更稳定，支持中英文，返回结构化数据。
"""

from __future__ import annotations

import re

def search(query: str, max_results: int = 5) -> list[dict]:
    """搜索网页，返回 [{title, url, snippet}]"""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
            for r in results if r.get("title")
        ]
    except Exception as e:
        return [{"title": f"搜索失败: {e}", "url": "", "snippet": ""}]


def search_formatted(query: str, max_results: int = 5) -> str:
    """搜索并格式化为文本"""
    results = search(query, max_results)
    if not results:
        return ""
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        if r.get('snippet'):
            lines.append(f"   {r['snippet'][:300]}")
        if r.get('url'):
            lines.append(f"   来源: {r['url']}")
    return "\n".join(lines)
