"""
Dongcode Skill 记忆系统 — 项目经验持久化

每个项目结束后，CEO 把教训总结成 skill 文件。
新项目启动时，相关 skill 自动加载到上下文。

skill 目录：
  ~/.dongcode/skills/           <- Dongcode 自己的 skill
  ~/.hermes/skills/              <- 同时扫描 Hermes skill（可选）

skill 文件格式：标准 markdown，含 frontmatter
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SKILL_DIR = Path.home() / ".dongcode" / "skills"
HERMES_SKILL_DIR = Path.home() / ".hermes" / "skills"

# ── 注册的插件工具缓存 ──
_registered_tools = None


def get_registered_tools(force_reload: bool = False) -> list:
    """
    扫描所有 skill，找出 dong-plugin 工具。
    返回: [{"name": "工具名", "description": "描述", "exec": "命令模板", "skill": "来源skill"}, ...]
    """
    global _registered_tools
    if _registered_tools is not None and not force_reload:
        return _registered_tools

    tools = []

    # ── 内置工具（无需插件 skill）──
    tools.append({
        "name": "web_search",
        "description": "搜索网络信息。当你需要查找资料、技术方案、最佳实践时使用",
        "exec": "builtin",
        "skill": "__builtin__",
    })

    for base_dir in [SKILL_DIR, HERMES_SKILL_DIR]:
        if not base_dir.exists():
            continue
        for f in base_dir.rglob("SKILL.md"):
            if _is_excluded(str(f)):
                continue
            try:
                text = f.read_text()
            except:
                continue

            # 检查是否为插件 skill
            if "dong-plugin: true" not in text and "dong-plugin:true" not in text:
                continue

            # 提取工具定义
            tool_blocks = re.findall(
                r'- name:\s*(\S+)\s*\n\s*description:\s*"([^"]*)"\s*\n\s*exec:\s*"([^"]*)"',
                text
            )
            for name, desc, exec_cmd in tool_blocks:
                tools.append({
                    "name": name,
                    "description": desc,
                    "exec": exec_cmd,
                    "skill": str(f.parent),
                })

    _registered_tools = tools
    return tools


def _call_builtin_tool(tool_name: str, **kwargs) -> str:
    """直接调用内置工具（不走子进程）"""
    if tool_name == "web_search":
        try:
            from .web_search import search_formatted
            query = kwargs.get("query") or kwargs.get("q", "")
            return search_formatted(query) if query else "请输入搜索词"
        except Exception as e:
            return f"<搜索失败: {e}>"
    return f"<未知内置工具: {tool_name}>"


def call_plugin_tool(tool_name: str, **kwargs) -> str:
    """
    调用插件工具。
    查找注册的工具，执行对应的命令。
    """
    tools = get_registered_tools()
    for t in tools:
        if t["name"] == tool_name:
            # 内置工具直接调用
            if t.get("exec") == "builtin" and t["skill"] == "__builtin__":
                return _call_builtin_tool(tool_name, **kwargs)
            cmd = t["exec"]
            # 替换 {arg} 占位符
            for k, v in kwargs.items():
                cmd = cmd.replace(f"{{{k}}}", str(v))
            import subprocess
            try:
                # 设置工作目录为 dongcode/，确保 web_search 可导入
                dongcode_dir = Path(__file__).parent
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=30,
                    cwd=str(dongcode_dir)
                )
                return result.stdout or result.stderr
            except subprocess.TimeoutExpired:
                return f"<TOOL_TIMEOUT: {tool_name}>"
            except Exception as e:
                return f"<TOOL_ERROR: {e}>"
    return f"<TOOL_NOT_FOUND: {tool_name}>"


def format_tools_for_prompt() -> str:
    """把注册的工具格式化成 CEO/工人可读的工具列表"""
    tools = get_registered_tools()
    if not tools:
        return "暂无可用插件工具"

    parts = ["🔌 可用插件工具:\n"]
    for t in tools:
        parts.append(f"  - {t['name']}: {t['description']}")
        parts.append(f"    用法: {t['exec']}")
    return "\n".join(parts)


# 需要排除的私有技能路径关键词
_EXCLUDE_SKILL_PATTERNS = [
    "commodity-simulation", "commodity-trading", "commodity-data-ingestion",
    "worldos", "world-os",
    "v6-", "v6_",
    "dongbao", "dong-bao",
    "hermia", "hermia-",
    "credentials-keeper",
    "brand-hermia",
    "column", "column-omega",
    "qqq",  # 期货相关内部技能
    "cargill",
    "oilmill", "oil-mill",
    "vessel",
    "rapeseed",
    "hermes-secretary",
    "w2-", "w2_",
    "shadow-",
    "counterfactual",
    "e09r",
    "agent-cortex",
    "agent-behavior",
    "agent-pressure",
    "agent-perception",
    "r2-0", "r2s-", "r3-", "r3s",
    "p1-", "p7d",
    "qf-layer",
    "quant-simulation",
    "price-model",
    "simulation-baseline",
    "commodity-feed",
    "commodity-evidence",
    "commodity-news",
    "commodity-report",
    "commodity-backtest",
    "commodity-text-trading",
    "commodity-research",
    "commodity-knowledge",
    "commodity-facility",
    "commodity-project",
    "multi-commodity",
    "risk-first",
    "trading-decision",
    "trader-factory",
    "text-trader",
    "cross-commodity",
    "crusher-behavior",
    "feedmill",
    "forward-simulation",
    "futures-simulation",
    "futures-trading",
    "independent-app",
    "modern-trader",
    "news-engine",
    "hermes-offline",
    "hermes-web-ui",
    "apk-", "apk_",
    "dongbao",
    "hermes-s6",
    "kc-data",
    "web-api-auth",
]


def _is_excluded(path: str) -> bool:
    """检查技能路径是否在排除列表中"""
    path_lower = path.lower()
    for pattern in _EXCLUDE_SKILL_PATTERNS:
        if pattern in path_lower:
            return True
    return False


def ensure_skill_dir() -> None:
    SKILL_DIR.mkdir(parents=True, exist_ok=True)


def save_project_skills(project_name: str, lessons: list, summary: str, ceo_llm_func: Any = None) -> None:
    """
    项目结束时调用。CEO 自己总结教训，写入 skill 文件。
    """
    ensure_skill_dir()

    if ceo_llm_func:
        lesson_lines = "\n".join([
            f"- {l.get('pattern', '')}: {l.get('detail', '')[:100]}"
            for l in lessons
        ])
        prompt = f"""项目 {project_name} 已完成。
以下是从项目中学到的教训列表：

{lesson_lines}

项目摘要：
{summary[:2000]}

请提炼出 3-5 条最重要的教训，写成一篇 skill 文档。
每条教训要包含：
1. 问题描述
2. 发生原因
3. 解决方案（可复用的做法）

输出格式：
```markdown
# 教训 1: 标题
问题：[描述]
原因：[根因]
解决：[怎么做]
```"""
        skill_content = ceo_llm_func(
            [{"role": "user", "content": prompt}],
            system="你是经验总结专家。把项目教训提炼成可直接复用的 skill。",
            max_tokens=2048, temp=0.3
        )
    else:
        skill_content = f"# {project_name} 项目经验\n\n"
        for l in lessons:
            skill_content += f"- {l.get('pattern', '')}: {l.get('detail', '')}\n"

    # 提取 skill 正文（去掉 markdown 代码标记）
    code_blocks = re.findall(r'```(?:markdown)?\n(.*?)```', skill_content, re.DOTALL)
    if code_blocks:
        skill_content = code_blocks[0]

    # 写 skill 文件
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', project_name.lower())
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    skill_file = SKILL_DIR / f"{safe_name}-{ts}.md"

    # 构造 tags
    tag_items = []
    for l in lessons[:3]:
        tag = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fff]', '', l.get('pattern', 'lesson'))
        tag_items.append(tag)
    tags_str = ",".join(tag_items)

    frontmatter = f"""---
name: {safe_name}
description: "{project_name} 项目经验教训"
tags: [{tags_str}]
created: {ts}
---

"""

    skill_file.write_text(frontmatter + skill_content)
    print(f"  [Skill] 已保存: {skill_file}")
    return skill_file


def load_relevant_skills(context_keywords: str = "") -> list:
    """
    新项目启动时调用。扫描 skills 目录，匹配关键词返回相关 skill。
    支持递归目录（Hermes 的多级分类结构）。
    """
    ensure_skill_dir()
    skills = []

    # 收集所有 skill 文件（递归扫描，排除内部技能）
    skill_files = []
    for base_dir in [SKILL_DIR, HERMES_SKILL_DIR]:
        if base_dir.exists():
            for f in base_dir.rglob("*.md"):
                if not _is_excluded(str(f)):
                    skill_files.append(f)

    # 如果没有关键词，返回最近的 3 个
    if not context_keywords:
        skill_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for f in skill_files[:3]:
            text = f.read_text()[:500] if f.exists() else ""
            skills.append({"file": str(f), "content": text})
        return skills

    # 关键词匹配
    keywords = context_keywords.lower().split()
    scored = []

    for f in skill_files:
        if not f.exists():
            continue
        try:
            text = f.read_text().lower()
        except Exception:
            continue

        score = 0

        # frontmatter 中的 name 和 tags 权重高
        frontmatter_match = re.search(r'^---\s*(.*?)\s*^---', text, re.MULTILINE | re.DOTALL)
        if frontmatter_match:
            fm = frontmatter_match.group(1).lower()
            for kw in keywords:
                if kw in fm:
                    score += 3  # frontmatter 匹配权重高

        # 正文匹配
        body = re.sub(r'^---.*?^---', '', text, count=1, flags=re.DOTALL | re.MULTILINE)
        for kw in keywords:
            count = body.count(kw)
            score += count

        # 文件名匹配权重更高
        fname = f.stem.lower()
        for kw in keywords:
            if kw in fname:
                score += 5

        # 目录名匹配（Hermes 的分类目录）
        parent_dirs = str(f.parent).lower()
        for kw in keywords:
            if kw in parent_dirs:
                score += 4

        if score > 0:
            scored.append((score, str(f), text[:1500]))

    scored.sort(reverse=True)
    return [{"file": f, "content": c} for _, f, c in scored[:5]]


def format_skills_for_prompt(skills: list) -> str:
    """把 skill 列表格式化成 CEO 可读的上下文"""
    if not skills:
        return ""

    parts = ["📚 相关经验（来自历史项目）:\n"]
    for s in skills[:3]:
        content = s.get("content", "")
        parts.append(content[:300])
        parts.append("---")
    return "\n".join(parts)
