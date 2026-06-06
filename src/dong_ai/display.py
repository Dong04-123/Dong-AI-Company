"""Dong AI — 终端显示引擎"""
import re, time
from pathlib import Path

class C:
    R = '\033[0m'
    B = '\033[1m'
    D = '\033[2m'
    I = '\033[3m'
    P = '\033[38;5;141m'
    G = '\033[38;5;244m'
    GN = '\033[38;5;78m'
    BL = '\033[38;5;75m'
    Y = '\033[38;5;221m'
    C2 = '\033[38;5;81m'
    W = '\033[38;5;255m'
    R2 = '\033[38;5;203m'
    BG = '\033[48;5;235m'

R, B, D, I = C.R, C.B, C.D, C.I
P, G, GN, BL = C.P, C.G, C.GN, C.BL
Y, C2, W, R2 = C.Y, C.C2, C.W, C.R2
BG = C.BG

WIDTH = 90


def box_top(label: str = ""):
    pad = WIDTH - len(label) - 6
    print(f"  {D}╭─{R} {B}{label}{R} {D}{'─'*max(0,pad)}╮{R}")


def box_bottom():
    print(f"  {D}╰{'─'* (WIDTH-2)}╯{R}")


def sep():
    print(f"  {D}{'─'* (WIDTH-2)}{R}")


def status_line(company: str, model: str, msgs: int, phase: str, score: str,
                state: dict = None, model_pool=None):
    icon = "⚡" if phase == "运行中" else "●"
    score_disp = f"{P}{score}{R}" if score != "—" else f"{G}—{R}"
    parts = [f"{GN}{icon}{R} {B}{company}{R}", f"{D}model:{R} {model}"]
    if state:
        n = len(state.get('projects', []))
        if n: parts.append(f"{D}project:{R} {n}")
    parts.append(f"{D}score:{R} {score_disp}")
    if state and state.get('start_time'):
        t = int(time.time() - state['start_time'])
        parts.append(f"{D}{t}s{R}")
    try:
        if model_pool:
            usage = model_pool.get_usage()
            t = usage.get('total', 0)
            if t: parts.append(f"{D}token:{R} {t//1000}K")
    except: pass
    print(f"  {'  '.join(parts)}")


def render_markdown(text: str) -> str:
    text = re.sub(r'```(\w*)\n(.*?)```',
        lambda m: f"\n{BG}{G}{'─'*50}{R}\n{m.group(2)}\n{BG}{G}{'─'*50}{R}\n",
        text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', f'{C2}\\1{R}', text)
    text = re.sub(r'\*\*(.+?)\*\*', f'{B}\\1{R}', text)
    return text


def print_assistant(text: str):
    rendered = render_markdown(text)
    for line in rendered.split('\n'):
        line = line.rstrip()
        if not line:
            print(f"  {D}┊{R}"); continue
        kws = {'招募':'◆','组建':'◆','分析':'■','战略':'■','方案':'■',
               '技术':'▶','开发':'▶','工程':'▶','执行':'▶','编码':'▶',
               '质量':'◆','测试':'◆','审核':'◆','审查':'◆',
               '评分':'★','综合':'★','总分':'★'}
        for kw, icon in kws.items():
            if kw in line:
                clr = P if icon in '◆■' else BL
                print(f"  {D}┊{R} {clr}{icon}{R} {line}")
                break
        else:
            print(f"  {D}┊{R} {line}")


def print_banner(name: str, model_name: str, mode: str, model_pool=None):
    """启动头：Logo + 专业信息"""
    logo = f"""  {P}{B}
  ██████╗  ██████╗ ███╗   ██╗ ██████╗     █████╗ ██╗
  ██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗██║
  ██║  ██║██║   ██║██╔██╗ ██║██║         ███████║██║
  ██║  ██║██║   ██║██║╚██╗██║██║         ██╔══██║██║
  ██████╔╝╚██████╔╝██║ ╚████║╚██████╗    ██║  ██║██║
  ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝  ╚═╝╚═╝
  {R}"""
    print(logo)

    # 实时系统信息
    providers_n = 0
    provider_list = []
    if model_pool:
        try:
            av = model_pool.available()
            providers_n = len(av)
            for p in av[:4]:
                provider_list.append(f"{p['id']}({p['models'][0]})")
        except: pass

    ver = getattr(__import__('dong_ai'), '__version__', '0.1.0')
    box_top(f"Dong AI  v{ver}")
    print(f"  {D}┊{R}")
    print(f"  {D}┊{R}  {B}{name}{R}  {D}│{R}  {GN}●{R} active  {D}│{R}  model: {B}{model_name}{R}")
    print(f"  {D}┊{R}")
    print(f"  {D}┊{R}  ■ 您的私人AI公司")
    if provider_list:
        print(f"  {D}┊{R}  {D}providers:{R} {', '.join(provider_list)}" +
              (f"  {D}(+{providers_n-4} more){R}" if providers_n > 4 else ""))

    # 硬件检测 + 本地服务器状态
    hw_info = ""
    local_status = ""
    try:
        import subprocess
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,name",
                           "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            line = r.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in line.split(",", 1)]
            mb = parts[0]
            name = parts[1] if len(parts) > 1 else ""
            hw_info = f"{name} ({mb}MB)"
    except: pass
    if not hw_info:
        try:
            r = subprocess.run(["free", "-m"], capture_output=True, text=True, timeout=2)
            for l in r.stdout.split("\n"):
                if l.startswith("Mem:"):
                    hw_info = f"CPU ({l.split()[1]}MB RAM)"
        except: pass

    # 检测本地模型服务是否在响应
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8080/v1/models",
                                     method="GET")
        urllib.request.urlopen(req, timeout=2)
        local_status = f"  {D}|{R}  local: {GN}●{R} responding"
    except:
        local_status = f"  {D}|{R}  local: {R2}○{R} offline"

    if hw_info:
        print(f"  {D}┊{R}  {D}hw:{R} {hw_info}{local_status}")
    print(f"  {D}┊{R}  {D}pipeline:{R} Design(红蓝辩论) → Plan(依赖拆解) → Execute(工人池+自愈+互审) → Review(董事会评分)")
    print(f"  {D}┊{R}  {D}stack:{R} Multi-agent · 3-tier memory · OpenAI API · Auto failover ({providers_n} providers) · 121 tests")
    print(f"  {D}┊{R}  {D}mode:{R} {mode}")
    print(f"  {D}┊{R}")
    print(f"  {D}┊{R}  {B}commands:{R}  /dash dashboard  /soul customize  /mode switch  /help  /exit")
    box_bottom()
