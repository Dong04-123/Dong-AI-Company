"""Dong AI — 交互式配置向导

用法:
  dong setup             完整向导（默认）
  dong setup model       仅配置模型
  dong setup context     仅配上下文窗口
"""

import os, sys, subprocess
from pathlib import Path
from dong_ai.model_pool import ModelPool, PROVIDERS
from dong_ai.ceo_memory import CEOMemory
from dong_ai.display import C

mem = CEOMemory()
pool = ModelPool()


def _ask(prompt: str, default: str = "") -> str:
    """带默认值的输入"""
    d = f" [{C.R}{default}{C.D}]" if default else ""
    val = input(f"  {C.D}{prompt}{d}:{C.R} ").strip()
    return val or default


def _title(n: int, text: str):
    print(f"\n  {C.P}{n}. {text}{C.R}")
    print(f"  {C.D}{'─'*50}{C.R}")


def _ok(text: str):
    print(f"  {C.GN}✓{C.R} {text}")


def _info(text: str):
    print(f"  {C.D}{text}{C.R}")


def _header():
    """向导顶栏"""
    print(f"\n  {C.B}╭{'─'*54}╮{C.R}")
    print(f"  {C.B}│{C.R}  {C.P}Dong AI Company{C.R}  配置向导{' '*(24)}│")
    print(f"  {C.B}│{C.R}  {C.D}一行命令，配好你的 AI 公司{' '*(18)}{C.R}  │")
    print(f"  {C.B}╰{'─'*54}╯{C.R}")


def _footer():
    print(f"\n  {C.GN}╭{'─'*54}╮{C.R}")
    print(f"  {C.GN}│{C.R}  {C.B}✔ 配置完成{C.R}")
    print(f"  {C.GN}│{C.R}  验证: {C.D}dong check{C.R}")
    print(f"  {C.GN}│{C.R}  运行: {C.D}dong run \"你的任务\"{C.R}")
    print(f"  {C.GN}│{C.R}  快捷: {C.D}dong make \"需求\"{C.R}")
    print(f"  {C.GN}╰{'─'*54}╯{C.R}")


def step_hardware():
    """Step 1: 检测硬件"""
    _title(1, "硬件检测")
    gpu = ""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,name",
                           "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            line = r.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",", 1)]
            gpu = f"{parts[1]} ({parts[0]}MB)"
    except:
        pass
    if gpu:
        _ok(f"GPU: {gpu}")
    else:
        _info("未检测到 GPU（CPU 模式）")


def step_mode():
    """Step 2: 选择运行模式"""
    _title(2, "运行模式")
    print(f"  {C.D}[1]{C.R}  云端模式 — API 调用（大窗口、快速）")
    print(f"  {C.D}[2]{C.R}  本地模式 — 本地模型（免费、隐私）")
    print(f"  {C.D}[3]{C.R}  自动检测（推荐）")
    choice = _ask("请输入编号", "3")
    mode = {"1": "api", "2": "local", "3": "auto"}.get(choice, "auto")
    mem.config_set("mode", mode)
    _ok(f"模式: {mode}")


def step_provider():
    """Step 3: 选择厂商 + 模型 + 配 key"""
    _title(3, "模型选择")

    # 分两组：已配置 key / 未配置
    all_providers = []
    configured = []
    unconfigured = []
    for i, (pid, info) in enumerate(PROVIDERS.items(), 1):
        env_name = info.get("env_key", "")
        has_key = bool(os.environ.get(env_name)) if env_name else False
        entry = {"id": pid, "name": info["name"], "models": info["models"],
                 "env_key": env_name, "has_key": has_key}
        all_providers.append(entry)
        (configured if has_key else unconfigured).append(entry)

    if configured:
        print(f"  {C.D}── 已配置（有 API Key）──{C.R}")
        for i, p in enumerate(configured, 1):
            key_s = os.environ.get(p["env_key"], "")[:6] + "…"
            print(f"  {C.D}[{i:2d}]{C.R}  {p['name']:<20} {C.GN}{key_s}{C.R}")

    print(f"  {C.D}── 未配置（需要 API Key）──{C.R}")
    offset = len(configured)
    for i, p in enumerate(unconfigured, offset + 1):
        print(f"  {C.D}[{i:2d}]{C.R}  {p['name']:<20} {C.D}未配置{C.R}")

    # 选厂商
    idx = int(_ask("选择厂商编号", "1")) - 1
    sel = all_providers[idx] if 0 <= idx < len(all_providers) else all_providers[0]

    # 选模型
    print(f"\n  {C.D}── {sel['name']} 模型 ──{C.R}")
    for i, m in enumerate(sel["models"], 1):
        tag = ""
        if i == 1:
            tag = f" {C.GN}(推荐){C.R}"
        print(f"  {C.D}[{i}]{C.R}  {m}{tag}")
    mi = int(_ask("选择模型编号", "1")) - 1
    model = sel["models"][mi] if 0 <= mi < len(sel["models"]) else sel["models"][0]

    mem.config_set("provider", sel["id"])
    mem.config_set("model", model)
    _ok(f"{sel['name']} → {model}")

    # 配 key
    if not sel["has_key"] and sel["env_key"]:
        print()
        key = input(f"  {C.D}输入 {sel['name']} API Key（留空跳过）:{C.R} ").strip()
        if key:
            env_path = Path.home() / ".hermes" / ".env"
            env_path.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            if env_path.exists():
                lines = [l for l in env_path.read_text().split("\n")
                         if l.strip() and not l.startswith(f"{sel['env_key']}=")]
            lines.append(f"{sel['env_key']}={key}")
            env_path.write_text("\n".join(lines) + "\n")
            os.environ[sel["env_key"]] = key
            _ok("API Key 已保存")


def step_context():
    """Step 4: 上下文窗口配置"""
    _title(4, "上下文窗口")
    print(f"  {C.D}建议保持默认值，高级用户可按需调整{C.R}")
    print()
    ceo = _ask("CEO 上下文", "64000")
    if ceo.isdigit(): mem.config_set("ceo_context", ceo)
    worker = _ask("Worker 上下文", "32000")
    if worker.isdigit(): mem.config_set("worker_context", worker)
    ceo_t = _ask("CEO 最大回复", "8192")
    if ceo_t.isdigit(): mem.config_set("ceo_max_tokens", ceo_t)
    worker_t = _ask("Worker 最大回复", "4096")
    if worker_t.isdigit(): mem.config_set("worker_max_tokens", worker_t)


def run_full():
    _header()
    step_hardware()
    step_mode()
    step_provider()
    step_context()
    _footer()


def run_model():
    _header()
    step_provider()


def run_context():
    step_context()


def main(args: list[str] = None):
    if args is None:
        args = sys.argv[2:]
    sub = args[0] if args else "full"

    if sub == "model":
        run_model()
    elif sub == "context":
        run_context()
    else:
        run_full()
