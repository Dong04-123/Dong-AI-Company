"""
Dong AI — 模型网关

用户配置多个 API Key，设主次分层，系统自动路由。
不必只用一家，不用担心单点故障。

用法:
  dong gateway list             查看所有 provider 状态
  dong gateway set deepseek     设为主力模型
  dong gateway tier deepseek cheap  标记为廉价层（用于研究）
  dong gateway tier openai expensive 标记为昂贵层（用于生成）
"""

import json, os
from pathlib import Path


_GATEWAY_FILE = Path.home() / ".dong" / "gateway.json"


def _load() -> dict:
    if _GATEWAY_FILE.exists():
        try:
            return json.loads(_GATEWAY_FILE.read_text())
        except Exception:
            pass
    return {"priority": [], "tiers": {}}


def _save(data: dict):
    _GATEWAY_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GATEWAY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def list_providers() -> list[dict]:
    """列出所有 provider 及其状态"""
    from .model_pool import PROVIDERS
    cfg = _load()
    result = []
    for pid, info in PROVIDERS.items():
        key = os.environ.get(info.get("env_key", ""), "")
        priority = cfg.get("priority", [])
        tiers = cfg.get("tiers", {})
        rank = priority.index(pid) + 1 if pid in priority else 99
        result.append({
            "id": pid,
            "name": info["name"],
            "has_key": bool(key),
            "models": info["models"],
            "priority": rank,
            "tier": tiers.get(pid, "auto"),
        })
    # 有 key 的排前面，有优先级的排最前
    result.sort(key=lambda p: (0 if p["has_key"] else 1, p["priority"]))
    return result


def set_priority(provider_id: str, rank: int = 1):
    """设置 provider 优先级"""
    cfg = _load()
    prio = cfg.get("priority", [])
    if provider_id in prio:
        prio.remove(provider_id)
    prio.insert(max(0, rank - 1), provider_id)
    cfg["priority"] = prio
    _save(cfg)


def set_tier(provider_id: str, tier: str):
    """设置 provider 分层 (cheap/expensive/auto)"""
    cfg = _load()
    tiers = cfg.get("tiers", {})
    if tier == "auto":
        tiers.pop(provider_id, None)
    else:
        tiers[provider_id] = tier
    cfg["tiers"] = tiers
    _save(cfg)


def resolve(task_type: str = "auto") -> dict | None:
    """按任务类型自动选择最优 provider

    task_type: "research" | "draft" | "analyze" | "quick" | "auto"
    """
    from .model_pool import PROVIDERS
    cfg = _load()
    tiers = cfg.get("tiers", {})

    all_providers = list_providers()
    if not all_providers:
        return None

    # 研究/分析类 → cheap 层优先
    cheap_target = task_type in ("research", "analyze", "quick")
    expensive_target = task_type in ("draft", "deploy")

    for p in all_providers:
        if not p["has_key"]:
            continue
        t = tiers.get(p["id"], "auto")
        if cheap_target and t == "cheap":
            return p
        if expensive_target and t == "expensive":
            return p
        if t == "auto":
            return p  # 第一个有 key 且没分层的

    # 兜底：第一个有 key 的
    for p in all_providers:
        if p["has_key"]:
            return p
    return None
