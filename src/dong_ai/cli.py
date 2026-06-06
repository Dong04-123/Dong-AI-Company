"""Dong AI — 命令行入口"""
from __future__ import annotations

import sys, os, json, time
from pathlib import Path


def _lang() -> str:
    """检测用户语言偏好"""
    l = os.environ.get("LANG", os.environ.get("LC_ALL", "zh_CN"))
    return "en" if l.startswith("en") else "zh"


_ = {
    "zh": {
        "help_title": "Dong AI Company — 您的私人AI公司",
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
    },
    "en": {
        "help_title": "Dong AI Company — Your Private AI Company",
        "quick_start": "Quick Start",
        "cmd_setup": "Interactive setup",
        "cmd_chat": "Start chat",
        "cmd_run": "One-click project",
        "cmd_serve": "Start API server",
        "mgmt": "Management",
        "auto": "Automation",
        "info": "Info",
        "unknown": "Unknown command",
        "available": "Available",
    },
}


def T(key: str) -> str:
    lang = _lang()
    return _.get(lang, _["zh"]).get(key, _["zh"].get(key, key))


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else ""

    if not cmd or cmd in ("-h", "--help", "help"):
        print(f"{T('help_title')}")
        print("=" * 50)
        print(f"{T('quick_start')}:  dong setup      {T('cmd_setup')}")
        print(f"           dong chat      {T('cmd_chat')}")
        print(f'           dong run "需求" {T("cmd_run")}')
        print(f"           dong serve     {T('cmd_serve')}")
        print("=" * 50)
        print(f"{T('mgmt')}:     config  skill  session  detect")
        print(f"{T('auto')}:    cron   webhook  mcp")
        print(f"{T('info')}:      version")
        return

    if cmd in ("-v", "--version", "version"):
        from dong_ai import __version__
        print(f"Dong AI Company v{__version__}"); return

    if cmd == "detect": return _cmd_detect()
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

    print(f"{T('unknown')}: {cmd}")
    print(f"{T('available')}: chat, run, serve, detect, config, skill, session, mcp, cron, webhook, setup, version")
    sys.exit(1)


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
    ceo = CEO()
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
            print("图记忆为空 — CEO 执行项目后自动填充")
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
    print("用法: dong graph [list|view <id>|merge <from> <to>]")

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

    # 4. 选择主模型
    print("┊")
    print("┊  📋 可用模型:")
    for i, p in enumerate(available[:10], 1):
        key_preview = p["api_key"][:8] + "..." if p["api_key"] else "无 key"
        print(f"┊    [{i}] {p['name']:<18} {p['models'][0]:<35} {key_preview}")
    if len(available) > 10:
        print(f"┊    ... 共 {len(available)} 个")

    model_choice = input("┊  选择主模型编号 (默认 1): ").strip()
    if model_choice and model_choice.isdigit():
        idx = int(model_choice) - 1
        if 0 <= idx < len(available):
            sel = available[idx]
            print(f"┊    主模型: {sel['name']} ({sel['models'][0]})")

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

    # 6. 保存并验证
    print("┊")
    print("┊  ✅ 配置已保存")
    print("┊")
    print("┊  快速验证:")
    print("┊    dong detect    查看可用模型")
    print("┊    dong chat      启动对话")
    print("┊    dong serve     启动 API 服务")
    print("┊    dong config list  查看全部配置")
    print("╰──────────────────────────────────────────────────╯")


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
