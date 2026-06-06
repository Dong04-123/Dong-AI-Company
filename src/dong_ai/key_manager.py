"""
Dong AI — API Key 管理器

持久化存储 API Key → tenant 映射，支持动态增删改查。
数据存在 ~/.dong/keys.json，运行时热加载。

CLI 命令:
  dong key create <tenant>    → 生成新 key
  dong key list               → 列出所有 key
  dong key revoke <key>       → 吊销 key
  dong key verify <key>       → 验证 key 的 tenant

环境变量（启动时加载）:
  DONG_API_KEY=sk-xxx                     → 默认 tenant "default"
  DONG_API_KEYS={"sk-xxx":"tenant-a"}     → 多租户映射
"""

from __future__ import annotations

import json, os, hashlib, secrets, time
from pathlib import Path
from typing import Optional


_KEY_FILE = Path.home() / ".dong" / "keys.json"


def _ensure_key_file() -> None:
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _KEY_FILE.exists():
        _KEY_FILE.write_text("{}")


def _load_keys() -> dict[str, dict]:
    """加载所有 key → tenant 映射"""
    _ensure_key_file()
    try:
        return json.loads(_KEY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_keys(keys: dict) -> None:
    """保存 key → tenant 映射"""
    _KEY_FILE.write_text(json.dumps(keys, indent=2, ensure_ascii=False))


def _generate_key() -> str:
    """生成安全的 sk-xxx 格式 API Key"""
    random_bytes = secrets.token_hex(24)  # 48 hex chars = 192 bits
    return f"sk-{random_bytes[:8]}-{random_bytes[8:24]}-{random_bytes[24:40]}-{random_bytes[40:]}"


def _key_fingerprint(key: str) -> str:
    """Key 指纹（用于日志，不暴露完整 key）"""
    return f"{key[:12]}...{key[-4:]}"


def create_key(tenant: str, description: str = "") -> str:
    """创建新的 API Key"""
    keys = _load_keys()
    new_key = _generate_key()
    keys[new_key] = {
        "tenant": tenant,
        "created_at": time.time(),
        "description": description or f"Key for {tenant}",
        "revoked": False,
        "fingerprint": _key_fingerprint(new_key),
    }
    _save_keys(keys)
    return new_key


def list_keys() -> list[dict]:
    """列出所有 API Key（不暴露完整 key）"""
    keys = _load_keys()
    result = []
    for k, v in keys.items():
        result.append({
            "fingerprint": v.get("fingerprint", _key_fingerprint(k)),
            "tenant": v["tenant"],
            "created_at": v.get("created_at", 0),
            "description": v.get("description", ""),
            "revoked": v.get("revoked", False),
        })
    return result


def revoke_key(key: str) -> bool:
    """吊销 API Key"""
    keys = _load_keys()
    if key not in keys:
        # 尝试指纹匹配（用户可能传指纹而非完整 key）
        for k, v in keys.items():
            if v.get("fingerprint") == key:
                v["revoked"] = True
                _save_keys(keys)
                return True
        return False
    keys[key]["revoked"] = True
    _save_keys(keys)
    return True


def verify_key(key: str) -> Optional[str]:
    """验证 API Key 有效并返回 tenant。无效返回 None"""
    keys = _load_keys()
    info = keys.get(key)
    if not info:
        return None
    if info.get("revoked", False):
        return None
    return info["tenant"]


def resolve_tenants() -> dict[str, str]:
    """合并环境变量 + 持久化的 key 映射"""
    result = {}

    # 1. 加载持久化的 key
    keys = _load_keys()
    for k, v in keys.items():
        if not v.get("revoked", False):
            result[k] = v["tenant"]

    # 2. 环境变量覆盖
    env_key = os.environ.get("DONG_API_KEY", "")
    if env_key:
        result[env_key] = "default"

    env_keys_json = os.environ.get("DONG_API_KEYS", "")
    if env_keys_json:
        try:
            extra = json.loads(env_keys_json)
            if isinstance(extra, dict):
                result.update(extra)
        except json.JSONDecodeError:
            pass

    return result
