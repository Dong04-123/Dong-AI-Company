"""
Dong AI — 多领域运营框架

每个领域是一个 Domain 子类，注册到 CompanyRuntime。
运行时自动调用 init() → tick() (每分钟) → report() (每日)

用法:
  dong company start --domain finance --domain novel
  dong company start --domain ecommerce
"""

import json, time, importlib, inspect
from pathlib import Path
from typing import Any


class Domain:
    """领域基类 — 所有领域插件继承此类"""

    name: str = "base"
    description: str = "基础领域"
    config_key: str = "domain_base"

    def __init__(self, runtime: Any, config: dict = None):
        self.runtime = runtime
        self.config = config or {}
        self.state: dict = {}
        self._tick_count = 0

    def init(self) -> None:
        """领域初始化 — 启动时调用"""
        pass

    def tick(self) -> None:
        """每分钟调用 — 核心逻辑"""
        self._tick_count += 1

    def on_event(self, event: str, payload: dict) -> dict | None:
        """事件处理 — webhook/告警等"""
        return None

    def report(self) -> str:
        """日报摘要 — 每天 9:00 调用"""
        return f"【{self.name}】运行中 ({self._tick_count} ticks)"

    def alert(self, message: str, level: str = "info") -> None:
        """发送告警/通知"""
        self.runtime._log(self.name, f"[{level}] {message}")

    def save_state(self) -> dict:
        return self.state

    def load_state(self, state: dict) -> None:
        self.state.update(state)

    @property
    def config_path(self) -> Path:
        return Path.home() / ".dong" / "domains" / f"{self.name}.json"


# ── 注册表 ──

_registry: dict[str, type[Domain]] = {}

def register(cls: type[Domain]) -> type[Domain]:
    """装饰器: 注册领域"""
    _registry[cls.name] = cls
    return cls

def get_domain(name: str) -> type[Domain] | None:
    return _registry.get(name)

def list_domains() -> list[str]:
    return list(_registry.keys())

def load_domains(runtime: Any, names: list[str],
                 configs: dict[str, str] = None) -> list[Domain]:
    """加载指定领域列表"""
    instances = []
    for name in names:
        cls = _registry.get(name)
        if cls:
            config = _load_config(cls)
            # Apply runtime configs (from CLI --domain flag)
            if configs and name in configs:
                config["prompt"] = config.get("prompt", "") + configs[name]
                config["description"] = configs[name]
            inst = cls(runtime, config)
            try:
                inst.init()
                instances.append(inst)
                runtime._log("domain", f"领域 {name} 已加载")
            except Exception as e:
                runtime._log("domain", f"领域 {name} 加载失败: {e}")
    return instances


def _load_config(cls: type[Domain]) -> dict:
    """加载领域配置"""
    path = Path.home() / ".dong" / "domains" / f"{cls.name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def init_default_domains():
    """加载所有内置领域模块"""
    for module_name in ["autonomous"]:
        try:
            importlib.import_module(f".{module_name}", __package__)
        except ImportError:
            pass
