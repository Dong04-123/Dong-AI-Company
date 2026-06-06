"""Dong AI — 终端显示引擎"""
from __future__ import annotations

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

WIDTH = 72


def box_top(label: str = "") -> None:
    pad = WIDTH - len(label) - 6
    print(f"  {D}╭─{R} {B}{label}{R} {D}{'─'*max(0,pad)}╮{R}")


def box_bottom() -> None:
    print(f"  {D}╰{'─'* (WIDTH-2)}╯{R}")


def sep() -> None:
    print(f"  {D}{'─'* (WIDTH-2)}{R}")


def status_line(company: str, model: str, msgs: int, phase: str, score: str,
                state: dict = None, model_pool=None) -> None:
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
            if t:
                ctx = state.get('_context_max', 64000) if state else 64000
                pct = min(100, int(t / ctx * 100)) if ctx else 0
                parts.append(f"{D}ctx:{R} {t//1000}K/{ctx//1000}K {pct}%")
            # 图记忆规模
            try:
                from dong_ai.datastore import get_repo
                gr = get_repo("graph")
                nodes = len(gr.get_project_nodes("current"))
                deps = len(gr.get_deps("current"))
                if nodes or deps:
                    parts.append(f"{D}graph:{R} {nodes}/{deps}")
            except: pass
    except: pass
    print(f"  {'  '.join(parts)}")


def render_markdown(text: str) -> str:
    text = re.sub(r'```(\w*)\n(.*?)```',
        lambda m: f"\n{BG}{G}{'─'*50}{R}\n{m.group(2)}\n{BG}{G}{'─'*50}{R}\n",
        text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', f'{C2}\\1{R}', text)
    text = re.sub(r'\*\*(.+?)\*\*', f'{B}\\1{R}', text)
    return text


def print_assistant(text: str) -> None:
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


def print_banner(name: str, model_name: str, mode: str, model_pool=None) -> None:
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
    if provider_list:
        print(f"  {D}┊{R}  {D}gateway:{R} {providers_n} providers  {D}|{R}  {D}primary:{R} {provider_list[0]}")
    print(f"  {D}┊{R}  {D}pipeline:{R} Design(红蓝辩论) → Plan → Execute(自愈+互审) → Review")
    print(f"  {D}┊{R}  {D}mode:{R} {mode}")
    print(f"  {D}┊{R}")
    print(f"  {D}┊{R}  {B}commands:{R}  /dash dashboard  /soul customize  /mode switch  /help  /exit")
    box_bottom()
