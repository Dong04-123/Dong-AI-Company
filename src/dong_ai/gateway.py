"""Dong AI — 模型网关

自动检测可用模型 → 任务类型匹配 → 自动 fallback。

任务类型:
  quick     快速轻量任务 → 最快响应
  research  研究/分析    → 高性价比 + 大上下文
  draft     生成/创作    → 最强模型
  analyze   代码/审计    → 最强 + 大上下文
  auto      自动匹配     → 根据模型能力推荐

用法:
  dong gateway list              查看所有 provider 状态
  dong gateway set deepseek      设为主力
  dong gateway tier deepseek cheap  标记为廉价层
"""

import json, os
from pathlib import Path

_GATEWAY_FILE = Path.home() / ".dong" / "gateway.json"

# 模型能力评分 (0-10)
_MODEL_CAPABILITIES = {
    "speed": {
        "deepseek-chat": 9, "deepseek-reasoner": 4,
        "gpt-4o": 7, "gpt-4o-mini": 10,
        "claude-sonnet-4": 5, "claude-haiku-3": 9,
        "gemini-2.0-flash": 9, "gemini-2.0-pro": 5,
        "llama-3.3-70b-versatile": 7, "llama-3.1-8b-instant": 10,
        "grok-beta": 6, "grok-2": 5,
        "qwen-plus": 7, "qwen-max": 5,
        "glm-4-plus": 6, "glm-4-air": 8,
        "moonshot-v1-8k": 8, "moonshot-v1-32k": 6,
        "MiniMax-Text-01": 5,
        "mimo-v2.5": 6, "mimo-v2.5-pro": 5,
        "command-r-plus": 5,
        "Meta-Llama-3.1-70B": 6, "Meta-Llama-3.1-8B": 9,
        "Qwen3.6-35B-A3B-UD-IQ4_NL": 7, "qwen3.5:9b": 8,
    },
    "quality": {
        "deepseek-chat": 8, "deepseek-reasoner": 9,
        "gpt-4o": 9, "gpt-4o-mini": 7,
        "claude-sonnet-4": 10, "claude-haiku-3": 8,
        "gemini-2.0-flash": 7, "gemini-2.0-pro": 9,
        "llama-3.3-70b-versatile": 7, "llama-3.1-8b-instant": 4,
        "grok-beta": 7, "grok-2": 8,
        "qwen-plus": 6, "qwen-max": 8,
        "glm-4-plus": 6, "glm-4-air": 5,
        "moonshot-v1-8k": 6, "moonshot-v1-32k": 6,
        "MiniMax-Text-01": 5,
        "mimo-v2.5": 5, "mimo-v2.5-pro": 6,
        "command-r-plus": 6,
        "Meta-Llama-3.1-70B": 6, "Meta-Llama-3.1-8B": 4,
        "Qwen3.6-35B-A3B-UD-IQ4_NL": 6, "qwen3.5:9b": 5,
    },
    "context": {
        "deepseek-chat": 8, "deepseek-reasoner": 8,
        "gpt-4o": 7, "gpt-4o-mini": 5,
        "claude-sonnet-4": 9, "claude-haiku-3": 7,
        "gemini-2.0-flash": 10, "gemini-2.0-pro": 10,
        "llama-3.3-70b-versatile": 6, "llama-3.1-8b-instant": 5,
        "grok-beta": 5, "grok-2": 5,
        "qwen-plus": 7, "qwen-max": 7,
        "glm-4-plus": 6, "glm-4-air": 5,
        "moonshot-v1-8k": 4, "moonshot-v1-32k": 6,
        "MiniMax-Text-01": 6,
        "mimo-v2.5": 5, "mimo-v2.5-pro": 6,
        "command-r-plus": 7,
        "Meta-Llama-3.1-70B": 6, "Meta-Llama-3.1-8B": 5,
        "Qwen3.6-35B-A3B-UD-IQ4_NL": 3, "qwen3.5:9b": 3,
    },
}

# 任务类型 → 最优权重: [速度, 质量, 上下文]
_TASK_PROFILES = {
    "quick":   {"speed": 1.0, "quality": 0.3, "context": 0.2},
    "research":{"speed": 0.3, "quality": 0.6, "context": 0.8},
    "draft":   {"speed": 0.2, "quality": 1.0, "context": 0.5},
    "analyze": {"speed": 0.2, "quality": 0.8, "context": 1.0},
    "code":    {"speed": 0.3, "quality": 1.0, "context": 0.6},
    "auto":    {"speed": 0.5, "quality": 0.7, "context": 0.5},
}

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

def _score_model(model_name: str, task_type: str) -> float:
    """给单个模型打分"""
    profile = _TASK_PROFILES.get(task_type, _TASK_PROFILES["auto"])
    caps = _MODEL_CAPABILITIES
    speed = caps["speed"].get(model_name, 5) * profile["speed"]
    quality = caps["quality"].get(model_name, 5) * profile["quality"]
    context = caps["context"].get(model_name, 5) * profile["context"]
    return speed + quality + context

def _best_model_for_provider(provider_id: str, models: list, task_type: str) -> str:
    """从 provider 的模型列表中找到最适合该任务的那个"""
    scored = [(_score_model(m, task_type), m) for m in models]
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]

def _score_provider(pid: str, task_type: str) -> float:
    """给 provider 打分（取其最佳模型分）"""
    from .model_pool import PROVIDERS
    models = PROVIDERS.get(pid, {}).get("models", [])
    if not models:
        return 0
    return max(_score_model(m, task_type) for m in models)

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
            "speed": max(_MODEL_CAPABILITIES["speed"].get(m, 5) for m in info["models"]),
            "quality": max(_MODEL_CAPABILITIES["quality"].get(m, 5) for m in info["models"]),
            "context_score": max(_MODEL_CAPABILITIES["context"].get(m, 5) for m in info["models"]),
        })
    # 有 key 的排前面，有优先级的排最前
    result.sort(key=lambda p: (0 if p["has_key"] else 1, p["priority"]))
    return result

def set_priority(provider_id: str, rank: int = 1):
    cfg = _load()
    prio = cfg.get("priority", [])
    if provider_id in prio:
        prio.remove(provider_id)
    prio.insert(max(0, rank - 1), provider_id)
    cfg["priority"] = prio
    _save(cfg)

def set_tier(provider_id: str, tier: str):
    cfg = _load()
    tiers = cfg.get("tiers", {})
    if tier == "auto":
        tiers.pop(provider_id, None)
    else:
        tiers[provider_id] = tier
    cfg["tiers"] = tiers
    _save(cfg)

def resolve(task_type: str = "auto") -> dict | None:
    """按任务类型自动路由到最佳 provider

    智能评分 + 分层约束 + fallback
    """
    from .model_pool import PROVIDERS
    cfg = _load()
    tiers = cfg.get("tiers", {})

    all_providers = list_providers()
    available = [p for p in all_providers if p["has_key"]]
    if not available:
        return None

    # 去掉用户明确设为某层的
    tier_filter = cfg.get("tiers", {})

    # Step 1: 按任务评分排序
    scored = []
    for p in available:
        score = _score_provider(p["id"], task_type)
        # 手动优先级加成 (优先级的权重)
        prio_bonus = max(0, 10 - p["priority"]) * 0.5 if p["priority"] < 50 else 0
        # 分层惩罚: cheap 层做 drafting 扣分, expensive 层做 quick 扣分
        user_tier = tier_filter.get(p["id"], "")
        tier_penalty = 0
        if user_tier == "cheap" and task_type in ("draft", "analyze", "code"):
            tier_penalty = 5
        if user_tier == "expensive" and task_type in ("quick", "research"):
            tier_penalty = 3
        final_score = score + prio_bonus - tier_penalty
        scored.append((final_score, p))

    scored.sort(key=lambda x: -x[0])

    # Step 2: 返回最佳 (含 fallback: 如果第一个失败, 调用方可重试下一个)
    best = scored[0][1]
    best_model = _best_model_for_provider(best["id"], PROVIDERS.get(best["id"], {}).get("models", []), task_type)
    return {**best, "selected_model": best_model}

def resolve_chain(task_type: str = "auto") -> list[dict]:
    """返回完整 fallback 链 — 按评分排序的所有可用 (provider, model) 对"""
    from .model_pool import PROVIDERS
    all_providers = list_providers()
    available = [p for p in all_providers if p["has_key"]]
    if not available:
        return []

    scored = []
    for p in available:
        score = _score_provider(p["id"], task_type)
        model = _best_model_for_provider(p["id"], PROVIDERS.get(p["id"], {}).get("models", []), task_type)
        scored.append((score, {**p, "selected_model": model}))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored]
