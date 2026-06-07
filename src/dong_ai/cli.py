"""Dong AI — 命令行入口"""
from __future__ import annotations

import sys, os, json, time
from pathlib import Path
from .display import C


def _lang() -> str:
    """检测用户语言偏好"""
    l = os.environ.get("LANG", os.environ.get("LC_ALL", "zh_CN"))
    return "en" if l.startswith("en") else "zh"


_DONG_RULE_CACHE: str | None = None
_QUICK_POOL_CACHE: tuple[float, object, object] | None = None  # (timestamp, pool, tool_ex)


def _get_quick_pool():
    """缓存 ModelPool 和 ToolExecutor，避免重复初始化"""
    global _QUICK_POOL_CACHE
    now = time.time()
    if _QUICK_POOL_CACHE and now - _QUICK_POOL_CACHE[0] < 30:
        return _QUICK_POOL_CACHE[1], _QUICK_POOL_CACHE[2]
    from .model_pool import ModelPool
    from .tool_executor import ToolExecutor
    pool = ModelPool()
    pool.available()  # warm cache
    tool_ex = ToolExecutor()
    _QUICK_POOL_CACHE = (now, pool, tool_ex)
    return pool, tool_ex

def _load_dong_rule() -> str:
    """从当前目录向上搜索 .dong_rule，返回规则文本"""
    global _DONG_RULE_CACHE
    if _DONG_RULE_CACHE is not None:
        return _DONG_RULE_CACHE

    for p in [Path.cwd()] + list(Path.cwd().parents)[:5]:
        rule = p / ".dong_rule"
        if rule.exists():
            text = rule.read_text().strip()
            _DONG_RULE_CACHE = f"\n【项目规则】\n{text}\n"
            return _DONG_RULE_CACHE
    _DONG_RULE_CACHE = ""
    return ""


def _cmd_init() -> None:
    """在当前目录创建 .dong_rule 模板"""
    fp = Path.cwd() / ".dong_rule"
    if fp.exists():
        print(f"  ⚠️ .dong_rule 已存在: {fp}")
        return
    content = """# Dong AI 项目规则
# 删掉不用的行，改成你的项目信息

# 项目名称
project: 我的项目

# 技术栈
language: Python
framework: 
database: 
test_framework: pytest

# 编码规范
style: Google Python Style
indent: 4 spaces
max_line_length: 100

# 约束
require_tests: true
require_type_hints: true
require_docstrings: true

# 不要做的事
avoid:
  - print() 调试（用 logging）
  - 硬编码配置（用环境变量）
  - 超过 500 行的函数
"""
    fp.write_text(content.lstrip(), encoding="utf-8")
    print(f"  ✅ 已创建 {fp}")
    print(f"  {C.D}编辑此文件配置项目规则，dong run/quick/analyze/edit 会自动读取{C.R}")


_ = {
    "zh": {
        "help_title": "Dong AI Company — 你的私人AI公司",
        "quick_start": "快速开始",
        "cmd_setup": "交互式配置",
        "cmd_chat": "启动对话",
        "cmd_run": "一键执行",
        "cmd_serve": "启动 API",
        "mgmt": "管理",
        "auto": "自动化",
        "info": "信息",
        "unknown": "未知命令",
        "available": "可用",
        "no_api_key": "  ❌ 未检测到 API Key",
        "setup_hint": "  {C.B}dong setup{C.R}  交互式配置",
        "free_opts": "  {C.D}  免费: DeepSeek(500万) | Ollama(免费) | OpenAI(5美元){C.R}",
        "graph_empty": "图记忆为空 — CEO 执行后自动填充",
        "graph_usage": "用法: dong graph [list|view <id>|merge <from> <to>]",
        "graph_nodata": "项目 {pid} 无图数据",
        "graph_merged": "已合并, 目标项目现有 {n} 个符号",
        "interrupted": "\n  Interrupted.",
    },
    "en": {
        "help_title": "Dong AI Company",
        "quick_start": "Quick Start",
        "cmd_setup": "Interactive setup",
        "cmd_chat": "Start chat",
        "cmd_run": "One-click execute",
        "cmd_serve": "Start API server",
        "mgmt": "Management",
        "auto": "Automation",
        "info": "Info",
        "unknown": "Unknown command",
        "available": "Available",
        "no_api_key": "  ❌ No API key detected",
        "setup_hint": "  {C.B}dong setup{C.R}  Configure (20+ providers)",
        "free_opts": "  {C.D}  Free: DeepSeek | Ollama | OpenAI{C.R}",
        "graph_empty": "Graph memory is empty — populated after running CEO",
        "graph_usage": "Usage: dong graph [list|view <id>|merge <from> <to>]",
        "graph_nodata": "Project {pid} has no graph data",
        "graph_merged": "Merged. Target now has {n} symbols",
        "interrupted": "\n  Interrupted.",
    },
}


def T(key: str) -> str:
    lang = _lang()
    return _.get(lang, _["zh"]).get(key, _["zh"].get(key, key))


def main() -> None:
    import signal
    signal.signal(signal.SIGINT, lambda s, f: (print("\n  Interrupted."), sys.exit(0)))
    args = sys.argv[1:]
    cmd = args[0] if args else ""

    if not cmd or cmd in ("-h", "--help", "help"):
        has_key = False
        try:
            from .model_pool import ModelPool
            pool = ModelPool()
            has_key = any(p.get("api_key") for p in pool.available())
        except Exception:
            pass

        if has_key:
            print(f"""
{C.D}██████╗  ██████╗ ███╗   ██╗ ██████╗     █████╗ ██╗
██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗██║
██║  ██║██║   ██║██╔██╗ ██║██║         ███████║██║
██║  ██║██║   ██║██║╚██╗██║██║         ██╔══██║██║
██████╔╝╚██████╔╝██║ ╚████║╚██████╗    ██║  ██║██║
╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝  ╚═╝╚═╝{C.R}
╭─ {C.B}Dong AI Company v{__import__('dong_ai').__version__}{C.R} {'─'*28}╮
┊                                                                              ┊
┊  {C.P}🏢 你的 AI 公司 — 什么领域都能做{C.R}                                      ┊
┊                                                                              ┊
┊  {C.B}dong make [需求]{C.R}    自学任何领域，研究→提案→执行                        ┊
┊    例: dong make "一份新能源车行业报告"                                          ┊
┊    例: dong make "一部3章科幻漫剧" --auto                                       ┊
┊    例: dong make "一个SaaS商业计划书"                                           ┊
┊                                                                              ┊
┊  {C.B}dong run [任务]{C.R}    完整公司管线（辩论+专家+评审）                       ┊
┊  {C.B}dong quick [任务]{C.R}  轻量执行，不经过董事会                               ┊
┊  {C.B}dong company start{C.R} 启动7x24后台，自动盯盘+日报+备份                    ┊
┊                                                                              ┊
┊  {C.D}管理: config | gateway | check | knowledge{C.R}                               ┊
╰──────────────────────────────────────────────────────────────────────────────╯""")
        else:
            print(f"""
{C.D}██████╗  ██████╗ ███╗   ██╗ ██████╗     █████╗ ██╗
██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗██║
██║  ██║██║   ██║██╔██╗ ██║██║         ███████║██║
██║  ██║██║   ██║██║╚██╗██║██║         ██╔══██║██║
██████╔╝╚██████╔╝██║ ╚████║╚██████╗    ██║  ██║██║
╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝  ╚═╝╚═╝{C.R}
╭─ {C.B}Dong AI Company v{__import__('dong_ai').__version__}{C.R} {'─'*28}╮
┊                                                                              ┊
┊  {C.P}🏢 你的 AI 公司 — 什么领域都能做{C.R}                                      ┊
┊                                                                              ┊
┊  需要一个大模型 API Key 来启动（行业标配）:                                  ┊
┊  {C.B}dong setup{C.R}    交互式配置（支持20种模型）                                 ┊
┊                                                                              ┊
┊  {C.D}免费选项:{C.R}                                                                ┊
┊    1. DeepSeek — 平台注册送500万token → platform.deepseek.com                   ┊
┊    2. Ollama  — 本地运行，完全免费 → ollama.ai                                ┊
┊    3. OpenAI  — 送5美元 → platform.openai.com                                 ┊
╰──────────────────────────────────────────────────────────────────────────────╯""")
        return

    if cmd in ("-v", "--version", "version"):
        from dong_ai import __version__
        print(f"Dong AI Company v{__version__}"); return

    if cmd in ("check", "doctor"): return _cmd_check()
    if cmd == "detect": return _cmd_detect()
    if cmd == "init": return _cmd_init()
    if cmd == "run": return _cmd_run(args[1:])
    if cmd == "serve": return _start_server(args[1:])
    if cmd == "config": return _cmd_config(args[1:])
    if cmd == "key": return _cmd_key(args[1:])
    if cmd == "skill": return _cmd_skill(args[1:])
    if cmd == "session": return _cmd_session(args[1:])
    if cmd == "plugin": return _cmd_plugin(args[1:])
    if cmd == "mcp": return _cmd_mcp(args[1:])
    if cmd == "cron": return _cmd_cron(args[1:])
    if cmd == "webhook": return _cmd_webhook(args[1:])
    if cmd == "setup": return _cmd_setup()
    if cmd == "graph": return _cmd_graph(args[1:])
    if cmd == "chat": return _start_tui()
    if cmd in ("update", "upgrade"): return _cmd_update()
    if cmd == "analyze": return _cmd_analyze(args[1:])

    # API Key 检查
    if cmd in ("run", "quick", "edit", "debug", "analyze"):
        try:
            from .model_pool import ModelPool
            pool = ModelPool()
            has_key = any(p.get("api_key") for p in pool.available())
            if not has_key:
                print(f"{T('no_api_key')}")
                print(f"{T('setup_hint')}")
                print(f"{T('free_opts')}")
                return
        except Exception:
            pass
    if cmd == "edit": return _cmd_edit(args[1:])
    if cmd == "quick": return _cmd_quick(args[1:])
    if cmd == "debug": return _cmd_debug(args[1:])
    if cmd == "company": return _cmd_company(args[1:])
    if cmd == "demo": from .demo import _cmd_demo; return _cmd_demo()
    if cmd in ("make", "vision"): return _cmd_make(args[1:])
    if cmd == "gateway": return _cmd_gateway(args[1:])
    print(f"{T('unknown')}: {cmd}")
    print(f"{T('available')}: demo, chat, run, serve, detect, config, skill, session, mcp, cron, webhook, setup, version")
    sys.exit(1)


def _cmd_check() -> None:
    """检测系统配置是否可用，给出修复建议"""
    from dong_ai.model_pool import ModelPool
    from dong_ai.key_manager import list_keys
    from dong_ai.ceo_memory import CEOMemory

    print(f"  {C.B}🔍 Dong AI 系统检测{C.R}")
    print(f"  {'─'*50}")

    issues = []
    ok_count = 0

    # 1. API Key 检测
    pool = ModelPool()
    available = pool.available()
    has_api = any(p.get("api_key") for p in available)
    has_local = any("local" in p["name"].lower() or "ollama" in p["name"].lower()
                    for p in available)
    if has_api:
        print(f"  {C.GN}✅{C.R} API Key 已配置 ({sum(1 for p in available if p.get('api_key'))} 个 provider)")
        ok_count += 1
    else:
        issues.append("未检测到 API Key → 运行 dong setup 配置")
        print(f"  {C.Y}⚠️{C.R} 未配置 API Key")

    # 2. 模型检测
    if available:
        print(f"  {C.GN}✅{C.R} 可用模型: {len(available)} 个")
        for p in available[:5]:
            api_hint = " (有 key)" if p.get("api_key") else " (无 key)"
            print(f"     {p['name']:<15} {p['models'][0][:30]}{api_hint}")
        ok_count += 1
    else:
        issues.append("没有可用模型 → 配置 API Key 或启动本地模型")
        print(f"  {C.Y}⚠️{C.R} 没有可用模型")

    # 3. 配置检测
    try:
        mem = CEOMemory()
        cfg = mem.config_load()
        mode = cfg.get("mode", "auto")
        print(f"  {C.GN}✅{C.R} 模式: {mode}")
        print(f"     CEO 上下文: {cfg.get('ceo_context', '?')}  |  Worker: {cfg.get('worker_context', '?')}")
        ok_count += 1
    except Exception as e:
        issues.append(f"配置读取失败: {e}")

    # 4. 版本检测
    try:
        import urllib.request, json
        req = urllib.request.Request("https://pypi.org/pypi/dong-ai/json",
                                     headers={"User-Agent": "dong-ai"})
        resp = json.loads(urllib.request.urlopen(req, timeout=5).read())
        latest = resp["info"]["version"]
        from dong_ai import __version__
        if latest == __version__:
            print(f"  {C.GN}✅{C.R} 版本 v{__version__} (最新)")
        else:
            print(f"  {C.Y}⚠️{C.R} 版本 v{__version__} (最新: v{latest}) → dong update")
        ok_count += 1
    except Exception:
        print(f"  {C.D}  版本检查跳过 (无网络){C.R}")

    print(f"  {'─'*50}")
    print(f"  {C.GN}{'✅' * ok_count} {ok_count}/4 检查通过{C.R}")

    if issues:
        print(f"\n  {C.Y}⚠️ 需要修复:{C.R}")
        for i, issue in enumerate(issues, 1):
            print(f"    {i}. {issue}")
        print(f"\n  {C.B}💡 快速修复: dong setup{C.R}")
    else:
        print(f"\n  {C.GN}✅ 一切就绪，开始使用:{C.R}")
        print(f"     dong run \"你的需求\"")


def _cmd_detect() -> None:
    from dong_ai.model_pool import ModelPool
    print(ModelPool().detect())
    # 显示内置 MCP 服务器
    from dong_ai.plugin_registry import list_plugins
    plugins = list_plugins()
    builtin = [p for p in plugins if p["status"] == "builtin"]
    if builtin:
        print(f"\n📦 内置 MCP 工具 ({len(builtin)}):")
        for p in builtin:
            print(f"   {p['name']:<20} {p['command']} {' '.join(p.get('args',[]))[:40]}")
    installed = [p for p in plugins if p["status"] == "installed"]
    if installed:
        print(f"\n🔌 已安装插件 ({len(installed)}):")
        for p in installed:
            print(f"   {p['name']:<20} {p['command']} {' '.join(p.get('args',[]))[:40]}")
    print("\n快速命令:")
    print("   dong plugin search         浏览插件市场")
    print("   dong plugin install <name> 安装插件")


def _cmd_run(args) -> None:
    request = " ".join(args) if args else ""
    if not request: print("用法: dong run \"需求\""); return
    from dong_ai.ceo import CEO
    ceo = CEO(project_dir=str(Path.cwd()))
    ceo.run(request)
    print(f"  报告: {ceo.report_path}")


# ── config ──

def _cmd_config(args) -> None:
    if not args or args[0] == "list": return _config_list()
    if args[0] == "get" and len(args) >= 2: return _config_get(args[1])
    if args[0] == "set" and len(args) >= 2 and "=" in args[1]:
        k, v = args[1].split("=", 1)
        return _config_set(k.strip(), v.strip())
    print("用法: dong config [list] [get key] [set key=val]")


def _config_list() -> None:
    from dong_ai.ceo_memory import CEOMemory
    mem = CEOMemory()
    cfg = mem.config_load()
    mode = cfg.get("mode", "auto")
    resolved = mem._resolve_mode(mode)
    print(f"运行模式: {mode} → 实际: {resolved}")
    print(f"{'='*40}")
    for k, v in sorted(cfg.items()):
        if k == "description": continue
        print(f"  {k:<20} = {v}")
    print()
    print("上下文配置（自由调整）:")
    print(f"  dong config set ceo_context=64000       # CEO 上下文窗口")
    print(f"  dong config set ceo_max_tokens=8192     # CEO 最大回复")
    print(f"  dong config set worker_context=16000    # 工人上下文窗口")
    print(f"  dong config set worker_max_tokens=4096  # 工人最大回复")
    print()
    print("模式切换:")
    print(f"  dong config set mode=api      # 云端：大窗口+宽松")
    print(f"  dong config set mode=local    # 本地：小窗口+积极")
    print(f"  dong config set mode=auto     # 自动检测")

def _config_get(key) -> None:
    from dong_ai.ceo_memory import CEOMemory
    val = CEOMemory().config_load().get(key)
    print(f"{key} = {val}" if val else f"未找到: {key}")


def _config_set(key, val) -> None:
    from dong_ai.ceo_memory import CEOMemory
    CEOMemory().config_set(key, val)
    print(f"  ✅ {key} = {val}")


# ── key ──

def _cmd_key(args) -> None:
    """API Key 管理"""
    if not args or args[0] == "list":
        from dong_ai.key_manager import list_keys
        keys = list_keys()
        if keys:
            print(f"API Keys ({len(keys)}):")
            for k in keys:
                revoked = " [已吊销]" if k["revoked"] else ""
                print(f"  {k['fingerprint']:<28} {k['tenant']:<16} {k['description'][:40]}{revoked}")
        else:
            print("无 API Key。用 dong key create <tenant> 创建")
        return
    if args[0] == "create":
        tenant = args[1] if len(args) > 1 else "default"
        desc = " ".join(args[2:]) if len(args) > 2 else ""
        from dong_ai.key_manager import create_key
        key = create_key(tenant, desc)
        print(f"  ✅ 已创建 API Key")
        print(f"     Tenant: {tenant}")
        print(f"     Key:    {key}")
        print(f"     ┌─────────────────────────────────────────────┐")
        print(f"     │  ⚠️  保存好此 key，生成后不会再次显示         │")
        print(f"     │  客户端: curl -H 'Authorization: Bearer *** │")
        print(f"     └─────────────────────────────────────────────┘")
        return
    if args[0] == "revoke" and len(args) >= 2:
        from dong_ai.key_manager import revoke_key
        if revoke_key(args[1]):
            print(f"  ✅ Key {args[1][:16]}... 已吊销")
        else:
            print(f"  ✗ 未找到 key")
        return
    if args[0] == "verify" and len(args) >= 2:
        from dong_ai.key_manager import verify_key
        tenant = verify_key(args[1])
        if tenant:
            print(f"  ✅ 有效: tenant={tenant}")
        else:
            print(f"  ✗ 无效或已吊销")
        return
    print("用法: dong key [list|create <tenant> [desc]|revoke <key/fingerprint>|verify <key>]")


# ── skill ──

def _cmd_skill(args) -> None:
    if not args or args[0] == "list": return _skill_list()
    if args[0] == "create" and len(args) >= 2: return _skill_create(args[1])
    print("用法: dong skill [list] [create name=desc]")


def _skill_list() -> None:
    from dong_ai.memory import get_registered_tools, SKILL_DIR, HERMES_SKILL_DIR
    tools = get_registered_tools()
    if tools:
        print(f"插件工具 ({len(tools)}):")
        for t in tools: print(f"  {t['name']:<20} {t['description'][:60]}")
        print()
    files = []
    for d in [SKILL_DIR, HERMES_SKILL_DIR]:
        if d.exists(): files.extend(sorted(d.rglob("SKILL.md")))
    if files:
        print(f"Skill ({len(files)}):")
        for f in files:
            try:
                name = next((l.split(":",1)[1].strip() for l in f.read_text().split("\n") if l.startswith("name:")), "")
                print(f"  {name:<20} {f.parent}")
            except: print(f"  (err) {f}")
    else: print("无 skill，用 dong skill create 创建")


def _skill_create(expr) -> None:
    from dong_ai.memory import SKILL_DIR, ensure_skill_dir
    name = expr.split("=")[0] if "=" in expr else expr
    desc = expr.split("=",1)[1] if "=" in expr else ""
    ensure_skill_dir()
    path = SKILL_DIR / f'{"".join(c for c in name.lower() if c.isalnum() or c in "-_") or "skill"}.md'
    if path.exists(): print(f"  ⚠️ 已存在: {path}"); return
    path.write_text(f"---\nname: {name}\ndescription: \"{desc}\"\ntags: []\ncreated: {time.strftime('%Y-%m-%d')}\n---\n\n# {name}\n\n{desc}\n")
    print(f"  ✅ {path}")


# ── session ──

def _cmd_session(args) -> None:
    if not args or args[0] == "list": return _session_list()
    if args[0] == "view" and len(args) >= 2: return _session_view(args[1])
    print("用法: dong session [list] [view id]")


def _session_list() -> None:
    from dong_ai.ceo_memory import CEOMemory
    sessions = CEOMemory().session_list(limit=20)
    if not sessions: print("无会话"); return
    print(f"会话 ({len(sessions)}):")
    for s in sessions: print(f"  {s['id']:<30} {s.get('title',''):<20} msgs:{s.get('msgs',0)}  {s.get('time','')[:16]}")


def _session_view(sid) -> None:
    from dong_ai.ceo_memory import CEOMemory
    data = CEOMemory().session_load(sid)
    msgs = data.get("messages", [])
    print(f"会话: {sid} ({len(msgs)} 条)")
    for m in msgs[-10:]:
        icon = {"user":"🗣","assistant":"🤖"}.get(m["role"],"⚙️")
        print(f"  {icon} [{m['role']}] {m['content'][:200]}")


# ── plugin ──

def _cmd_plugin(args) -> None:
    """插件管理"""
    from dong_ai.plugin_registry import list_plugins, search_registry, install_plugin, remove_plugin
    if not args or args[0] == "list":
        plugins = list_plugins()
        if plugins:
            print(f"插件 ({len(plugins)}):")
            for p in plugins:
                status_icon = "🔌" if p["status"] == "installed" else "📦"
                env_hint = " 🔑" if p.get("env") else ""
                print(f"  {status_icon} {p['name']:<24} {p['status']:<8} {p['command']} {' '.join(p.get('args',[]))[:40]}{env_hint}")
        else:
            print("未安装 MCP 插件。用 dong plugin search 查看可用插件")
            print("  dong plugin install <name>  # 安装")
        return
    if args[0] == "search":
        query = " ".join(args[1:]) if len(args) > 1 else ""
        results = search_registry(query)
        if results:
            print(f"插件注册表 ({len(results)}):")
            print()
            for r in results:
                tags = ", ".join(r.get("tags", []))
                print(f"  {r['id']:<24} {r['name']}")
                print(f"  {'':24} {r['description'][:80]}")
                print(f"  {'':24} 命令: {r['command']} {' '.join(r['args'][:3])}...")
                if r.get("env"):
                    print(f"  {'':24} 需要环境变量: {', '.join(r['env'].keys())}")
                print()
        else:
            print(f"未找到匹配: {query}" if query else "注册表为空")
        return
    if args[0] == "install" and len(args) >= 2:
        install_plugin(args[1])
        return
    if args[0] == "remove" and len(args) >= 2:
        remove_plugin(args[1])
        return
    print("用法: dong plugin [list|search|install <name>|remove <name>]")
    print("       dong plugin search [关键词]  # 搜索注册表")


# ── mcp ──

def _cmd_mcp(args) -> None:
    return _mcp_discover(None)


def _mcp_discover(_server=None) -> None:
    import json
    servers = []
    for p in [Path.home()/".cursor"/"mcp.json", Path.cwd()/".mcp.json"]:
        if p.exists():
            try:
                data = json.loads(p.read_text())
                for n,c in data.get("mcpServers",data.get("servers",{})).items():
                    if isinstance(c,dict) and c.get("command"):
                        servers.append({"name":n,"command":c["command"],"args":str(c.get("args",""))[:60],"source":str(p)})
            except: pass
    # Hermes config
    hc = Path.home()/".hermes"/"config.yaml"
    if hc.exists():
        import re
        try:
            t=hc.read_text(); in_srv=False; cur=None
            for l in t.split("\n"):
                if re.match(r'^\s+servers:',l): in_srv=True; continue
                if in_srv:
                    m=re.match(r'^\s{4}(\w[\w-]*):',l)
                    if m: cur=m.group(1); continue
                    if cur and re.match(r'^\s{6}command:',l):
                        servers.append({"name":cur,"command":l.split(":",1)[1].strip().strip("'\"")}); cur=None
                    elif not l.startswith(" "): break
        except: pass
    if servers:
        print(f"MCP 服务器 ({len(servers)}):")
        for s in servers: print(f"  {s['name']:<20} {s['command']} {s['args']}")
        print("\n连接中...")
        for s in servers:
            try:
                from dong_ai.mcp_client import MCPClient
                c=MCPClient(s["name"],s["command"],s.get("args",[]))
                if c.connect():
                    tl=c.list_tools()
                    if tl: print(f"\n  {s['name']} ({len(tl)} 工具):")
                    for t in tl: print(f"    {t.get('name','?'):<25} {t.get('description','')[:60]}")
                    c.disconnect()
            except Exception as e: print(f"  ⚠️ {s['name']}: {e}")
    else:
        print("未发现 MCP 服务器。配置 .mcp.json 或 ~/.hermes/config.yaml")
        print('示例: {"mcpServers":{"fs":{"command":"npx","args":["-y","@modelcontextprotocol/server-filesystem","/tmp"]}}}')


# ── cron ──

def _cmd_cron(args) -> None:
    if not args or args[0] == "list": from dong_ai.cron import list_tasks; list_tasks(); return
    if args[0] == "add":
        name="未命名"; cmd=""; interval="1h"
        for i,a in enumerate(args):
            if a=="--name" and i+1<len(args): name=args[i+1]
            if a=="--cmd" and i+1<len(args): cmd=args[i+1]
            if a=="--every" and i+1<len(args): interval=args[i+1]
        if not cmd: print("需要 --cmd"); return
        from dong_ai.cron import add_task; add_task(name,cmd,interval); return
    if args[0]=="remove" and len(args)>=2: from dong_ai.cron import remove_task; remove_task(args[1]); return
    if args[0]=="start":
        from dong_ai.cron import CronScheduler
        s=CronScheduler(); s.start()
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt: s.stop()
        return
    print("用法: dong cron [list|add --cmd '...' --every 30m|remove <id>|start]")


# ── webhook ──

def _cmd_webhook(args) -> None:
    from dong_ai.cron import CRON_FILE
    f = CRON_FILE.parent / "webhooks.json"
    if not args or args[0]=="list":
        if f.exists():
            hooks=json.loads(f.read_text())
            if hooks:
                print(f"Webhooks ({len(hooks)}):")
                for h in hooks: print(f"  {h['name']:<20} {h.get('url','')}")
                return
        print("无 webhook 配置"); return
    if args[0]=="set-url" and len(args)>=2:
        hooks=json.loads(f.read_text()) if f.exists() else []
        hooks.append({"name":f"webhook_{len(hooks)+1}","url":args[1],"created":time.time()})
        f.parent.mkdir(parents=True,exist_ok=True); f.write_text(json.dumps(hooks,ensure_ascii=False,indent=2))
        print(f"  ✅ 已配置, POST {args[1]}/webhook"); return
    print("用法: dong webhook [list|set-url <url>]")

# ═══════════════════════════════════════════════════════════
# graph — 图记忆管理
# ═══════════════════════════════════════════════════════════

def _cmd_graph(args) -> None:
    """查看和管理图记忆"""
    from dong_ai.datastore import get_repo
    gr = get_repo("graph")
    if not args or args[0] == "list":
        projects = gr.list_projects()
        if not projects:
            print(T("graph_empty"))
            return
        total_nodes = sum(p["nodes"] for p in projects)
        total_deps = sum(p["deps"] for p in projects)
        print(f"图记忆: {len(projects)} 个项目, {total_nodes} 符号, {total_deps} 依赖")
        print()
        for p in projects:
            print(f"  {p['id']:<30} {p['nodes']:>4} 符号 ({p['functions']} 函数, {p['classes']} 类)  {p['deps']} 依赖")
        return
    if args[0] == "view" and len(args) >= 2:
        pid = args[1]
        kw = args[2:] if len(args) > 2 else None
        ctx = gr.format_context(pid, kw)
        print(ctx if ctx else f"项目 {pid} 无图数据")
        return
    if args[0] == "merge" and len(args) >= 3:
        n = gr.merge_project(args[1], args[2])
        print(f"已合并, 目标项目现有 {n} 个符号")
        return
    print(T("graph_usage"))

# ═══════════════════════════════════════════════════════════
# setup — 交互式配置向导
# ═══════════════════════════════════════════════════════════

def _cmd_setup() -> None:
    """交互式配置向导——检测硬件、选模型、设上下文"""
    from dong_ai.model_pool import ModelPool, PROVIDERS
    from dong_ai.ceo_memory import CEOMemory
    import subprocess

    mem = CEOMemory()
    pool = ModelPool()

    print("╭─ Dong AI 配置向导 ────────────────────────────────╮")
    print("┊")

    # 1. 硬件检测
    print("┊  🔍 检测硬件...")
    gpu_info = ""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,name",
                           "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            line = r.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",", 1)]
            gpu_info = f"{parts[1]} ({parts[0]}MB)" if len(parts) > 1 else f"{parts[0]}MB"
            print(f"┊     GPU: {gpu_info}")
    except: pass

    # 2. 模型检测
    available = pool.available()
    print(f"┊     发现 {len(available)} 个可用 provider")

    # 3. 选择模式
    print("┊")
    print("┊  📋 选择运行模式:")
    print("┊    [1] 云端模式 — 使用 API（大窗口、快速）")
    print("┊    [2] 本地模式 — 使用本地模型（免费、隐私）")
    print("┊    [3] 自动检测（推荐）")
    choice = input("┊  请输入 [1/2/3] (默认 3): ").strip() or "3"

    mode_map = {"1": "api", "2": "local", "3": "auto"}
    mode = mode_map.get(choice, "auto")
    mem.config_set("mode", mode)
    print(f"┊    模式已设为: {mode}")

    # 4. 选择主模型（列出所有已知 provider 及其所有模型）
    print("┊")
    print("┊  📋 可用模型:")
    all_providers = []
    for i, (pid, info) in enumerate(PROVIDERS.items(), 1):
        env_name = info.get("env_key", "")
        has_key = bool(os.environ.get(env_name)) if env_name else False
        key_preview = os.environ.get(env_name, "")[:8] + "..." if has_key else "无 key"
        models_str = ", ".join(info["models"][:4])
        if len(info["models"]) > 4:
            models_str += f"... (+{len(info['models'])-4})"
        all_providers.append({"id": pid, "name": info["name"], "models": info["models"],
                              "env_key": env_name, "has_key": has_key})
        print(f"┊    [{i:2d}] {info['name']:<18} {key_preview:<10} {models_str}")
    print(f"┊    ... 共 {len(all_providers)} 个 provider" if len(all_providers) > 10 else "")

    model_choice = input("┊  选择主模型编号 (默认 1): ").strip() or "1"
    sel = None
    sel_model = None
    if model_choice.isdigit():
        idx = int(model_choice) - 1
        if 0 <= idx < len(all_providers):
            sel = all_providers[idx]
            models = sel["models"]
            print(f"┊    ── {sel['name']} 的模型 ──")
            for mi, m in enumerate(models, 1):
                print(f"┊      [{mi}] {m}")
            model_idx = input(f"┊  选择模型编号 (默认 1): ").strip() or "1"
            if model_idx.isdigit():
                mi = int(model_idx) - 1
                if 0 <= mi < len(models):
                    sel_model = models[mi]
            if not sel_model:
                sel_model = models[0]
            print(f"┊    主模型: {sel['name']} ({sel_model})")
            mem.config_set("provider", sel["id"])
            mem.config_set("model", sel_model)

    # 4.5 API Key 录入
    if sel and not sel.get("has_key"):
        print("┊")
        print(f"┊  📋 {sel['name']} 需要 API Key")
        env_key_name = PROVIDERS.get(sel["id"], {}).get("env_key", "")
        if env_key_name:
            new_key = input(f"┊  输入 {sel['name']} API Key (留空跳过): ").strip()
            if new_key:
                # 写入 ~/.hermes/.env
                env_path = Path.home() / ".hermes" / ".env"
                env_path.parent.mkdir(parents=True, exist_ok=True)
                env_lines = []
                if env_path.exists():
                    env_lines = [l for l in env_path.read_text().split("\n")
                                 if l.strip() and not l.startswith(f"{env_key_name}=")]
                env_lines.append(f"{env_key_name}={new_key}")
                env_path.write_text("\n".join(env_lines) + "\n")
                # 设到当前环境
                os.environ[env_key_name] = new_key
                print(f"┊  ✅ {sel['name']} 已配置")
    # 5. 上下文配置
    print("┊")
    print("┊  📋 上下文窗口配置（输入数字，直接回车使用推荐值）:")
    ceo_ctx = input(f"┊    CEO 上下文 (推荐 64000): ").strip()
    if ceo_ctx.isdigit(): mem.config_set("ceo_context", ceo_ctx)
    worker_ctx = input(f"┊    工人上下文 (推荐 32000): ").strip()
    if worker_ctx.isdigit(): mem.config_set("worker_context", worker_ctx)
    ceo_tokens = input(f"┊    CEO 最大回复 (推荐 8192): ").strip()
    if ceo_tokens.isdigit(): mem.config_set("ceo_max_tokens", ceo_tokens)
    worker_tokens = input(f"┊    工人最大回复 (推荐 4096): ").strip()
    if worker_tokens.isdigit(): mem.config_set("worker_max_tokens", worker_tokens)

    # 6. 完成
    print("┊")
    print("┊  ✅ 配置已保存")
    print("┊")
    print("┊  快速验证:")
    print("┊    dong detect    查看可用模型")
    print("┊    dong chat      启动对话")
    print("┊    dong serve     启动 API 服务")
    print("┊    dong config list  查看全部配置")
    print("╰──────────────────────────────────────────────────╯")


def _cmd_make(args: list[str]) -> None:
    """Self-directed making — AI company researches, proposes, executes any output"""
    auto = "--auto" in args or "-a" in args
    request = " ".join(a for a in args if not a.startswith("--"))

    if not request:
        print(f"  Usage: {C.B}dong make <what to make> [--auto]{C.R}")
        print(f"\n  Examples:")
        print(f"    {C.D}dong make \"一部3章科幻漫剧\"{C.R}")
        print(f"    {C.D}dong make \"一份新能源车行业分析报告\"{C.R}")
        print(f"    {C.D}dong make \"一个SaaS产品的商业计划书\" --auto{C.R}")
        print(f"    {C.D}dong make \"一套API自动化测试方案\"{C.R}")
        print(f"    {C.D}dong make \"一款独立游戏的GDD文档\"{C.R}")
        print(f"    {C.D}dong make \"一份城市骑行路线的调研报告\"{C.R}")
        return

    from .vision import VisionPipeline
    vp = VisionPipeline(request, auto=auto)
    try:
        vp.run()
    except KeyboardInterrupt:
        print(f"\n  Interrupted. State saved.")


# ── gateway ──

def _gateway_best_task(pid: str) -> str:
    """返回 provider 最适合的任务类型"""
    from .gateway import _TASK_PROFILES, _score_provider
    from .model_pool import PROVIDERS
    best_task = "auto"
    best_score = -1
    for task in _TASK_PROFILES:
        if task == "auto":
            continue
        score = _score_provider(pid, task)
        if score > best_score:
            best_score = score
            best_task = task
    labels = {"quick": "快速响应", "research": "研究分析", "draft": "生成创作", "analyze": "深度分析", "code": "代码生成"}
    return labels.get(best_task, best_task)

def _cmd_gateway(args: list[str]) -> None:
    """模型网关 — 管理多个 API Key 的优先级和分层"""
    from .gateway import list_providers, set_priority, set_tier, resolve

    cmd = args[0] if args else "list"

    if cmd == "list":
        providers = list_providers()
        if not providers:
            print(f"  ⚠️  未检测到 API Key")
            print(f"  {C.B}dong setup{C.R}  配置 API Key")
            return

        print(f"\n  {C.B}Gateway — 可用模型{C.R}")
        print(f"  {'─'*65}")
        print(f"  {'Provider':<18} {'速度':>5} {'质量':>5} {'上下文':>5} {'任务':<20}")
        print(f"  {'─'*65}")
        for p in providers:
            status = "●" if p["has_key"] else "○"
            task = _gateway_best_task(p["id"])
            models_str = ", ".join(p["models"][:2])
            if len(p["models"]) > 2:
                models_str += f"..."
            print(f"  {status} {p['id']:<16} {p['speed']:>4}  {p['quality']:>4}  {p['context_score']:>4}  {task:<12} {models_str}")
        print(f"  {'─'*65}")
        providers_with_keys = [p for p in providers if p["has_key"]]
        if providers_with_keys:
            print(f"  {C.D}智能路由:{C.R}")
            for task in ["quick", "research", "draft", "analyze", "code"]:
                from .gateway import resolve, resolve_chain
                r = resolve(task)
                chain = resolve_chain(task)
                if r:
                    model = r.get("selected_model", r["models"][0])
                    names = [f"{c['id']}({c.get('selected_model',c['models'][0])})" for c in chain[:3]]
                    print(f"    {task:<12} → {C.B}{r['id']}/{model}{C.R}  (fallback: {', '.join(names[1:])})")
        return
    elif cmd == "set" and len(args) >= 2:
        set_priority(args[1])
        print(f"  ✅ 已设 {args[1]} 为首选")

    elif cmd == "tier" and len(args) >= 3:
        set_tier(args[1], args[2])
        print(f"  ✅ {args[1]} → {args[2]}")

    else:
        print(f"  用法:")
        print(f"    {C.B}dong gateway list{C.R}              查看所有 provider")
        print(f"    {C.B}dong gateway set <provider>{C.R}    设为首选")
        print(f"    {C.B}dong gateway tier <p> <层级>{C.R}    设分层 (cheap/expensive/auto)")


# ── update / upgrade ──

def _cmd_update() -> None:
    """检查并升级到最新版本"""
    import subprocess, sys, json, urllib.request
    from dong_ai import __version__

    print(f"  当前版本: v{__version__}")

    # 检查 PyPI
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/dong-ai/json",
            headers={"User-Agent": "dong-ai/0.1.0"},
        )
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
        latest = resp["info"]["version"]
        print(f"  PyPI 最新: v{latest}")

        if latest == __version__:
            print(f"  ✅ 已是最新版本")
            return
    except Exception as e:
        print(f"  ⚠️ 检查更新失败: {e}")
        return

    # 升级
    print(f"  ⬆️  升级到 v{latest}...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "dong-ai"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  ✅ 升级成功: v{__version__} → v{latest}")
        print(f"  重新运行 'dong' 即可使用新版本")
    else:
        print(f"  ❌ 升级失败: {result.stderr[:200]}")


# ── analyze ──

def _cmd_analyze(args: list[str]) -> None:
    """快速代码问答 — 对标「拖进Claude就问」"""
    filepath = args[0] if args else ""
    question = " ".join(args[1:]) if len(args) > 1 else "解释这段代码"

    if not filepath:
        print(f"  用法: {C.B}dong analyze <file> [问题]{C.R}")
        print(f"  示例: {C.D}dong analyze src/dong_ai/ceo.py 这个类的职责是什么？{C.R}")
        return

    fp = Path(filepath).expanduser()
    if not fp.exists():
        print(f"  ❌ 文件不存在: {fp}")
        return

    content = fp.read_text(encoding="utf-8", errors="replace")
    print(f"  {C.D}📄 {fp} ({len(content)} 字符){C.R}")
    print(f"  {C.B}❓ {question}{C.R}")
    print()

    # 直接调用 LLM，不经过 CEO
    from .model_pool import ModelPool
    pool = ModelPool()
    try:
        for token in pool.call_stream(
            [{"role": "user", "content": f"文件内容：\n```\n{content[:8000]}\n```\n\n问题：{question}"}],
            system=f"你是一个代码分析专家。简洁准确地回答。{_load_dong_rule()}",
            max_tokens=2048, temperature=0.3,
        ):
            print(token, end='', flush=True)
        print()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
    except Exception as e:
        print(f"  ❌ {e}")


# ── edit ──

def _cmd_edit(args: list[str]) -> None:
    """读文件 → 问需求 → diff → 写入 — 对标 Cursor 编辑"""
    filepath = args[0] if args else ""
    instruction = " ".join(args[1:]) if len(args) > 1 else ""

    if not filepath:
        print(f"  用法: {C.B}dong edit <file> [修改说明]{C.R}")
        print(f"  示例: {C.D}dong edit src/main.py 加一个--verbose参数{C.R}")
        return

    fp = Path(filepath).expanduser()
    if not fp.exists():
        print(f"  ❌ 文件不存在: {fp}")
        return

    content = fp.read_text(encoding="utf-8", errors="replace")
    print(f"  {C.D}📄 {fp} ({len(content)} 字符){C.R}")
    print(f"  {C.B}✏️  {instruction or '请描述修改需求...'}{C.R}")

    if not instruction:
        instruction = input(f"  {C.P}❯{C.R} 描述修改: ").strip()
        if not instruction:
            return

    # LLM 生成新代码
    from .model_pool import ModelPool
    pool = ModelPool()
    prompt = (
        f"当前文件内容：\n```\n{content[:12000]}\n```\n\n"
        f"修改要求：{instruction}\n\n"
        f"输出完整的新文件内容（不要省略号，不要省略，完整输出），"
        f"并简要解释改了什么。"
    )
    resp = ""
    try:
        for token in pool.call_stream(
            [{"role": "user", "content": prompt}],
            system=f"代码编辑专家。输出完整的文件内容。{_load_dong_rule()}",
            max_tokens=16384, temperature=0.3,
        ):
            resp += token
            print(token, end='', flush=True)
        print()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return
    except Exception as e:
        print(f"  ❌ {e}")
        return

    # 提取新代码
    import re
    code_match = re.search(r'```(?:\w+)?\n(.*?)```', resp, re.DOTALL)
    new_content = code_match.group(1) if code_match else resp
    new_content = new_content.strip()

    if not new_content or len(new_content) < 10:
        print(f"  ❌ 未能生成有效的代码")
        return

    # 显示 diff
    import difflib
    old_lines = content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    diff = list(difflib.unified_diff(old_lines, new_lines,
                                      fromfile=str(fp), tofile=str(fp)))
    changed = sum(1 for l in diff if l.startswith('+') or l.startswith('-'))
    if changed < 3:
        print(f"  {C.D}  无实质变更{C.R}")
        return

    print(f"\n  {C.Y}📊 变更: {changed} 行{C.R}")
    for l in diff[:20]:
        if l.startswith('+'):
            print(f"  {C.GN}{l.rstrip()}{C.R}")
        elif l.startswith('-'):
            print(f"  {C.R2}{l.rstrip()}{C.R}")
        elif l.startswith('@@'):
            print(f"  {C.D}{l.rstrip()}{C.R}")

    if len(diff) > 20:
        print(f"  {C.D}  ... 共 {len(diff)} 行差异{C.R}")

    # 确认写入
    confirm = input(f"\n  {C.P}❯{C.R} 应用修改？(Y/n): ").strip().lower()
    if confirm and confirm != 'y':
        print(f"  {C.D}  已取消{C.R}")
        return

    fp.write_text(new_content, encoding="utf-8")
    print(f"  {C.GN}✅ 已写入 {fp}{C.R}")


# ── quick ──

def _cmd_quick(args: list[str]) -> None:
    """轻量快速模式 — 绕过 CEO 管线，直接调用 LLM + 工具"""
    request = " ".join(args) if args else ""
    if not request:
        print(f"  用法: {C.B}dong quick <需求>{C.R}")
        print(f"  示例: {C.D}dong quick 在当前目录创建 README.md{C.R}")
        return

    # 立即显示 spinner，让用户感知"已经开始"
    print(f"  {C.B}⚡ {C.R}", end='', flush=True)
    import itertools, threading
    done = [False]
    def _spin():
        for c in itertools.cycle(['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']):
            if done[0]: break
            sys.stdout.write(f"\r  {C.D}{c} 思考中...{C.R}")
            sys.stdout.flush()
            time.sleep(0.08)
    spinner = threading.Thread(target=_spin, daemon=True)
    spinner.start()

    pool, tool_ex = _get_quick_pool()
    done[0] = True
    sys.stdout.write(f"\r  {' ' * 20}\r")
    sys.stdout.flush()

    system = (
        f"你是一个高效的 AI 助手。直接执行用户需求。\n"
        f"可用工具:\n"
        f"  [TOOL_CALL:read_file] path=路径\n"
        f"  [TOOL_CALL:write_file] path=路径 content=内容\n"
        f"  [TOOL_CALL:run] cmd=命令\n"
        f"  [TOOL_CALL:web_search] query=搜索词\n"
        f"  [TOOL_CALL:web_fetch] url=网页地址\n"
        f"简洁、直接、不废话。{_load_dong_rule()}"
    )

    msgs = [{"role": "system", "content": system},
            {"role": "user", "content": request}]
    resp = ""
    try:
        for token in pool.call_stream(msgs, system=system, max_tokens=4096):
            resp += token
            print(token, end='', flush=True)
        print()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return
    except Exception as e:
        print(f"  ❌ {e}")
        return

    # 工具执行
    results = tool_ex.execute_all(resp)
    for name, params, result in results:
        print(f"  {C.D}🔧 {name}: {result[:200]}{C.R}")
        if len(result) > 200:
            print(f"  {C.D}     ...{C.R}")


# ── debug ──

def _cmd_debug(args: list[str]) -> None:
    """CI 失败根因分析 — 拉日志+查图记忆+定根因+给修复"""
    import urllib.request, json, zipfile, io, re, os

    token = os.environ.get("GH_TOKEN", "")
    if not token:
        # Try reading from file
        try:
            token = open("/tmp/gh_token.txt").read().strip()
        except Exception:
            pass
    if not token:
        print(f"  ❌ 需要 GitHub Token: 设置 GH_TOKEN 环境变量")
        return

    repo = "Dong04-123/Dong-AI-Company"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    run_id = args[0] if args else ""

    def _gh(path: str) -> dict:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/{path}",
                                     headers=headers)
        return json.loads(urllib.request.urlopen(req, timeout=15).read())

    # 1. 获取运行
    if run_id:
        try:
            run = _gh(f"actions/runs/{run_id}")
        except Exception as e:
            print(f"  ❌ 找不到运行 #{run_id}: {e}")
            return
    else:
        runs = _gh("actions/runs?per_page=5&status=failure")["workflow_runs"]
        if not runs:
            print(f"  {C.GN}✅ 没有失败的 CI 运行{C.R}")
            return
        print(f"  {C.Y}最近的失败运行:{C.R}")
        for i, r in enumerate(runs[:5], 1):
            print(f"    [{i}] #{r['run_number']} {r['name']} — {r['head_branch']} ({r['created_at'][:10]})")
        choice = input(f"\n  {C.P}❯{C.R} 选择 (1-{min(5,len(runs))}): ").strip()
        try:
            run = runs[int(choice) - 1] if choice else runs[0]
        except (ValueError, IndexError):
            run = runs[0]
        run_id = str(run["id"])

    print(f"\n  {C.B}🔍 Debug CI #{run['run_number']} — {run['name']}{C.R}")
    print(f"  {C.D}  {run['html_url']}{C.R}")

    # 2. 拉日志
    print(f"\n  {C.D}📥 拉取日志...{C.R}")
    try:
        req = urllib.request.Request(run["logs_url"], headers=headers)
        resp = urllib.request.urlopen(req, timeout=30)
        log_data = resp.read()
    except Exception as e:
        print(f"  ❌ 拉取日志失败: {e}")
        return

    # 3. 解析日志 — 找报错文件+行号
    log_text = ""
    # Try as zip
    try:
        z = zipfile.ZipFile(io.BytesIO(log_data))
        for name in z.namelist():
            if "test_" in name or "Run tests" in name or "failure" in name or "error" in name:
                log_text += z.read(name).decode("utf-8", errors="replace") + "\n"
        if not log_text:
            for name in z.namelist():
                log_text += z.read(name).decode("utf-8", errors="replace") + "\n"
    except zipfile.BadZipFile:
        log_text = log_data.decode("utf-8", errors="replace")

    # 截取关键部分
    error_lines = []
    for line in log_text.split("\n"):
        lower = line.lower()
        if any(kw in lower for kw in ["error", "failed", "traceback", "assertionerror",
                                       "modulenotfounderror", "importerror",
                                       "syntaxerror", "valueerror", "typeerror",
                                       "keyerror", "attributeerror", "filenotfounderror"]):
            error_lines.append(line.strip())
    error_section = "\n".join(error_lines[:60])
    log_preview = log_text[-5000:] if len(log_text) > 5000 else log_text

    if error_lines:
        print(f"\n  {C.R2}❌ 发现 {len(error_lines)} 个错误/失败行{C.R}")
    else:
        print(f"\n  ⚠️ 未找到明确的报错信息")

    # 4. 从日志提取文件路径和行号
    file_refs = re.findall(r'File\s+\"([^\"]+)\",\s*line\s+(\d+)', log_text)
    source_refs = re.findall(r'([\w/]+\.py):(\d+)', log_text)
    file_refs.extend((f, l) for f, l in source_refs if not any(f == x[0] for x in file_refs))

    # 去重+过滤
    seen = set()
    unique_refs = []
    for f, l in file_refs:
        key = f"{f}:{l}"
        if key not in seen and (f.endswith(".py") or ".py:" in f):
            seen.add(key)
            unique_refs.append((f, l))

    source_context = ""
    if unique_refs:
        print(f"\n  📄 涉及文件 ({len(unique_refs)} 处):")
        for f, l in unique_refs[:8]:
            fp = Path(f)
            if not fp.is_absolute():
                fp = Path.cwd() / f
            if fp.exists():
                lines = fp.read_text().splitlines()
                start = max(0, int(l) - 5)
                end = min(len(lines), int(l) + 5)
                snippet = "\n".join(
                    f"  {C.R2 if i+1==int(l) else C.D}{i+1:4d}{' ❯' if i+1==int(l) else'  '}{lines[i]}{C.R}"
                    for i in range(start, end)
                )
                print(f"\n  {C.Y}{f}:{l}{C.R}")
                print(snippet)
                source_context += f"\n--- {f}:{l} ---\n" + "\n".join(lines[start:end]) + "\n"
            else:
                print(f"  {C.D}{f}:{l} (本地不存在){C.R}")

    # 5. 查图记忆
    graph_context = ""
    try:
        from .datastore import get_repo
        gr = get_repo("graph")
        projects = gr.list_projects()
        for proj in projects[:3]:
            pid = proj["id"]
            for f, l in unique_refs[:5]:
                fname = Path(f).name if f else ""
                if fname:
                    matches = gr.query(fname, pid)
                    if matches:
                        ctx = gr.format_context(pid, [fname])
                        if ctx:
                            graph_context += f"\n{ctx}\n"
    except Exception:
        pass

    # 6. LLM 根因分析
    print(f"\n  {C.B}🧠 AI 根因分析...{C.R}")
    from .model_pool import ModelPool
    pool = ModelPool()

    prompt = f"""CI 运行 #{run['run_number']} 失败。
分支: {run['head_branch']}
提交: {run.get('head_commit',{}).get('message','')[:100] if isinstance(run.get('head_commit'),dict) else ''}

## 错误日志
```
{error_section[:3000]}
```

## 日志末尾
```
{log_preview[:2000]}
```

## 源代码上下文
{source_context[:3000]}

## 图记忆中的代码结构
{graph_context[:2000]}

请分析:
1. 根因是什么（具体到文件和函数）
2. 为什么会发生
3. 修复方案（具体改什么）
4. 风险评估（影响范围）
"""

    analysis = ""
    try:
        for token in pool.call_stream(
            [{"role": "user", "content": prompt}],
            system=f"你是一个资深 DevOps 工程师。分析 CI 失败根因。简洁、精准、给出可操作的修复步骤。{_load_dong_rule()}",
            max_tokens=4096, temperature=0.2,
        ):
            analysis += token
            print(token, end='', flush=True)
        print()
    except KeyboardInterrupt:
        print("\n  Interrupted.")
        return
    except Exception as e:
        print(f"  ❌ LLM 分析失败: {e}")
        analysis = ""

    # 7. 保存报告
    report_dir = Path.home() / ".dong" / "debug"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"ci_{run['run_number']}_{run_id}.md"
    report = f"""# CI Debug Report — #{run['run_number']}

- **Name**: {run['name']}
- **Branch**: {run['head_branch']}
- **URL**: {run['html_url']}

## Errors Found
{len(error_lines)} error lines detected
{len(unique_refs)} file references

## Root Cause Analysis
{analysis}

## Files Involved
""" + "\n".join(f"- {f}:{l}" for f, l in unique_refs[:15]) + "\n"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n  {C.D}📝 报告已保存: {report_path}{C.R}")

    if analysis:
        print(f"\n  {C.GN}💡 执行修复: dong edit <file> \"修复此问题\"{C.R}")


# ── company ──

def _cmd_company(args: list[str]) -> None:
    """管理 7x24 AI 公司实例"""
    cmd = args[0] if args else "status"
    # 解析 --domain, --duration, --until 参数
    domain_names = []
    domain_prompts = {}
    duration = ""
    until = ""
    filtered = []
    i = 1
    while i < len(args):
        a = args[i]
        if a.startswith("--domain="):
            domain_names.append(a.split("=", 1)[1])
        elif a == "--domain" and i + 1 < len(args):
            val = args[i + 1]
            from dong_ai.domains import list_domains, init_default_domains
            init_default_domains()
            if val in list_domains():
                domain_names.append(val)
            else:
                domain_names.append("auto")
                domain_prompts["auto"] = domain_prompts.get("auto", "") + val + "; "
            i += 1
        elif a.startswith("--duration="):
            duration = a.split("=", 1)[1]
        elif a == "--duration" and i + 1 < len(args):
            duration = args[i + 1]; i += 1
        elif a.startswith("--until="):
            until = a.split("=", 1)[1]
        elif a == "--until" and i + 1 < len(args):
            until = args[i + 1]; i += 1
        else:
            if not a.startswith("--"):
                filtered.append(a)
        i += 1

    name = filtered[0] if filtered else "default"

    # 自动检测 domain/duration/until 配置
    config_file = Path.home() / ".dong" / f"company_{name}.json"
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text())
            if not domain_names:
                domain_names = cfg.get("domains", [])
            if not duration and not until:
                duration = cfg.get("duration", "")
                until = cfg.get("until", "")
        except Exception:
            pass

    from .company import CompanyRuntime
    cr = CompanyRuntime(name, domains=domain_names, domain_configs=domain_prompts,
                        duration=duration, until=until)

    if cmd == "start":
        cr.start()
    elif cmd == "stop":
        cr.stop()
    elif cmd == "restart":
        cr.stop()
        cr.start()
    elif cmd == "confirm":
        idx = int(filtered[1]) if len(filtered) > 1 else -1
        print(cr.governor.confirm(idx))
    elif cmd == "reject":
        idx = int(filtered[1]) if len(filtered) > 1 else -1
        print(cr.governor.reject(idx))
    elif cmd == "review":
        print(cr.governor.self_review())
    elif cmd == "knowledge":
        from .metacognition import MetacognitionEngine
        meta = MetacognitionEngine()
        print(meta.knowledge_map())
    elif cmd == "evolve":
        from .metacognition import MetacognitionEngine
        meta = MetacognitionEngine()
        result = meta.evolve_strategy()
        print(result or "✅ 当前无需调整学习策略")
    elif cmd == "status":
        s = cr.status()
        if s["state"] == "running":
            print(f"""
╭─ {C.B}🏢 Dong AI Company — {s['name']}{C.R} ─────────────────╮
┊                                                                              ┊
┊  状态: {C.GN}● 运行中{C.R}                                                       ┊
┊  运行时长: {s['uptime']//3600}h {(s['uptime']%3600)//60}m                                    ┊
┊  工单处理: {s['webhooks_received']}                                                     ┊
┊  任务完成: {s['tasks_completed']}                                                     ┊
┊  🌐 领域: {', '.join(s.get('domains',['无']))[:40]}                        ┊
┊  🔔 待确认: {len(cr.governor.pending_decisions())} 项                                        ┊
┊  最新日报: {s.get('last_daily_report','无')[:40]}                        ┊
┊                                                                              ┊
┊  {C.D}命令:{C.R}                                                                  ┊
┊    {C.B}dong company stop{C.R}     停止                                            ┊
┊    {C.B}dong company status{C.R}   查看状态                                        ┊
╰──────────────────────────────────────────────────────────────────────────────╯""")
        else:
            print(f"""
╭─ {C.D}🏢 Dong AI Company — {s['name']}{C.R} ─────────────────╮
┊                                                                              ┊
┊  状态: ○ 已停止                                                              ┊
┊  历史工单: {s['webhooks_received']}                                                     ┊
┊                                                                              ┊
┊  {C.B}dong company start{C.R}    启动 7x24 运营                                    ┊
╰──────────────────────────────────────────────────────────────────────────────╯""")
    else:
        print(f"  用法: {C.B}dong company <start|stop|status|restart> [name]{C.R}")
        print(f"  示例: {C.D}dong company start{C.R}")


# ═══════════════════════════════════════════════════════════
# TUI / Server

def _start_tui() -> None:
    from dong_ai.tui import main as t
    t()


def _start_server(args) -> None:
    try: import uvicorn
    except ImportError: print("需要: pip install 'dong-ai[server]'"); sys.exit(1)
    host, port = "0.0.0.0", 8648
    for i,a in enumerate(args):
        if a in ("-h","--host") and i+1<len(args): host=args[i+1]
        if a in ("-p","--port") and i+1<len(args): port=int(args[i+1])
    print(f"  🚀 Dong AI API on http://{host}:{port}")
    uvicorn.run("dong_ai.api:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
