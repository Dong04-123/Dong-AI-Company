"""Dong AI Company — 模型池

职责: Provider 配置发现 + 自动 failover 调用
HTTP 调用统一委托给 llm.py 的 OpenAICompatibleClient。

用法:
  pool = ModelPool()
  pool.best()          → 返回当前最优可用的模型配置
  pool.call(prompt)    → 自动 failover 调用
  pool.call_stream()   → 流式输出
"""
from __future__ import annotations

import os, json, time
from pathlib import Path


# ── 所有支持的 Provider ──
PROVIDERS = {
    # === OpenAI 兼容 API ===
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "env_key": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "provider_type": "openai",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "provider_type": "openai",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet", "google/gemini-pro"],
        "provider_type": "openai",
    },
    "kimi": {
        "name": "Kimi / Moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "env_key": "KIMI_API_KEY",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k"],
        "provider_type": "openai",
    },
    "dashscope": {
        "name": "Alibaba DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "env_key": "DASHSCOPE_API_KEY",
        "models": ["qwen-plus", "qwen-max"],
        "provider_type": "openai",
    },
    "glm": {
        "name": "Z.AI / GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "env_key": "GLM_API_KEY",
        "models": ["glm-4-plus", "glm-4-air"],
        "provider_type": "openai",
    },
    "xiaomi": {
        "name": "Xiaomi MiMo",
        "base_url": "https://api.xiaomi.com/v1",
        "env_key": "XIAOMI_API_KEY",
        "models": ["mimo-v2.5", "mimo-v2.5-pro"],
        "provider_type": "openai",
    },
    "minimax": {
        "name": "MiniMax",
        "base_url": "https://api.minimax.chat/v1",
        "env_key": "MINIMAX_API_KEY",
        "models": ["MiniMax-Text-01"],
        "provider_type": "openai",
    },
    "xai": {
        "name": "xAI / Grok",
        "base_url": "https://api.x.ai/v1",
        "env_key": "XAI_API_KEY",
        "models": ["grok-beta", "grok-2"],
        "provider_type": "openai",
    },
    "google": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "env_key": "GOOGLE_API_KEY",
        "models": ["gemini-2.0-flash", "gemini-2.0-pro"],
        "provider_type": "google",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1",
        "env_key": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4", "claude-haiku-3"],
        "provider_type": "anthropic",
    },
    "huggingface": {
        "name": "HuggingFace",
        "base_url": "https://api-inference.huggingface.co/models",
        "env_key": "HF_TOKEN",
        "models": ["meta-llama/Llama-3.3-70B"],
        "provider_type": "openai",
    },
    # === 热门开源/免费 API ===
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
        "provider_type": "openai",
    },
    "together": {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "models": ["meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"],
        "provider_type": "openai",
    },
    "fireworks": {
        "name": "Fireworks AI",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "env_key": "FIREWORKS_API_KEY",
        "models": ["accounts/fireworks/models/llama-v3p1-70b-instruct"],
        "provider_type": "openai",
    },
    "cerebras": {
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "env_key": "CEREBRAS_API_KEY",
        "models": ["llama3.1-8b", "llama3.1-70b"],
        "provider_type": "openai",
    },
    "cohere": {
        "name": "Cohere",
        "base_url": "https://api.cohere.com/v1",
        "env_key": "COHERE_API_KEY",
        "models": ["command-r-plus", "command-r"],
        "provider_type": "openai",
    },
    "deepinfra": {
        "name": "DeepInfra",
        "base_url": "https://api.deepinfra.com/v1/openai",
        "env_key": "DEEPINFRA_API_KEY",
        "models": ["meta-llama/Meta-Llama-3.1-70B-Instruct"],
        "provider_type": "openai",
    },

    # === 本地模型 ===
    "local": {
        "name": "本地模型",
        "base_url": "http://localhost:8080/v1",
        "env_key": "",
        "models": ["Qwen3.6-35B-A3B-UD-IQ4_NL.gguf"],
        "provider_type": "openai",
    },
    "ollama": {
        "name": "Ollama",
        "base_url": "http://localhost:11434/v1",
        "env_key": "",
        "models": ["qwen3.5:9b", "llama3:8b"],
        "provider_type": "openai",
    },
}


class ModelPool:
    """模型池 — 自动探测可用 provider，故障切换"""

    def __init__(self) -> None:
        self._cache = None
        self._last_usage = {"prompt": 0, "completion": 0, "total": 0}
        self._total_usage = {"prompt": 0, "completion": 0, "total": 0}
        self._load_env()

    def get_usage(self) -> dict:
        return dict(self._total_usage)

    def reset_usage(self) -> None:
        self._total_usage = {"prompt": 0, "completion": 0, "total": 0}

    def _load_env(self) -> None:
        """从 .hermes/.env 加载环境变量"""
        env_paths = [
            Path.home() / ".hermes" / ".env",
            Path.home() / ".env",
            Path.cwd() / ".env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                for line in env_path.read_text().split("\n"):
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        if k not in os.environ:
                            os.environ[k] = v

    def available(self) -> list:
        """返回所有可用的 provider（有 API key 或本地的）"""
        if self._cache is not None:
            return self._cache

        available = []
        for pid, cfg in PROVIDERS.items():
            key = os.environ.get(cfg["env_key"]) if cfg["env_key"] else ""
            if cfg["env_key"] and not key:
                continue
            available.append({
                "id": pid,
                "name": cfg["name"],
                "base_url": cfg["base_url"],
                "api_key": key,
                "models": cfg["models"],
                "type": cfg["provider_type"],
            })

        # 根据运行模式排序
        try:
            from .ceo_memory import CEOMemory
            mode = CEOMemory().config_load().get("mode", "auto")
        except Exception:
            mode = "auto"
        known_local = {"local", "ollama"}

        if mode == "local":
            # 本地模式：本地模型优先，有 key 的 API 排后面
            available.sort(key=lambda p: (
                0 if p["id"] in known_local else 1,
                0 if p["api_key"] else 1,
            ))
        else:
            # API 模式 / Auto：有 key 优先，本地模型最后
            available.sort(key=lambda p: (
                0 if p["api_key"] else 1,
                1 if p["id"] in known_local else 0,
                len(p["models"]),
            ))

        self._cache = available
        return available

    def best(self) -> dict:
        providers = self.available()
        if not providers:
            raise RuntimeError("没有可用的模型。请设置 DEEPSEEK_API_KEY 或启动本地模型。")
        return providers[0]

    def _make_client(self, provider: dict, timeout: int = 120):
        """从 provider 配置创建 LLM 客户端"""
        from .llm import LLMConfig, OpenAICompatibleClient
        config = LLMConfig(
            model=provider["models"][0],
            base_url=provider["base_url"],
            api_key=provider.get("api_key", ""),
            timeout=timeout,
        )
        return OpenAICompatibleClient(config)

    def call(self, messages: list, system: str = "", max_tokens: int = 4096,
             temperature: float = 0.3, timeout: int = 120) -> str:
        """自动 failover 调用。先试最优，失败自动切下一个。"""
        providers = self.available()
        last_error = ""

        for p in providers:
            try:
                client = self._make_client(p, timeout)
                resp = client.chat(messages, system,
                                   max_tokens=max_tokens, temperature=temperature)
                self._last_usage = dict(resp.usage)
                for k in self._last_usage:
                    self._total_usage[k] += self._last_usage[k]
                return resp.text
            except Exception as e:
                last_error = str(e)
                print(f"  [Model] {p['name']} 失败: {str(e)[:50]}")
                continue

        raise RuntimeError(f"所有模型不可用。最后错误: {last_error}")

    def call_stream(self, messages: list, system: str = "", max_tokens: int = 8192,
                    temperature: float = 0.7, timeout: int = 120):
        """流式调用，逐个 yield token。自动 failover。"""
        providers = self.available()
        last_error = ""
        for p in providers:
            try:
                client = self._make_client(p, timeout)
                # 流式调用后合并 usage
                total_usage = {"prompt": 0, "completion": 0, "total": 0}
                for token in client.chat_stream(messages, system,
                                                 max_tokens=max_tokens,
                                                 temperature=temperature):
                    yield token
                self._last_usage = dict(client._usage_total)
                for k in self._last_usage:
                    self._total_usage[k] += self._last_usage[k]
                return
            except Exception as e:
                last_error = str(e)
                continue
        raise RuntimeError(f"所有模型不可用。最后错误: {last_error}")

    def detect(self) -> str:
        """检测当前环境有哪些模型可用，返回摘要"""
        providers = self.available()
        if not providers:
            return "⚠️ 没有可用模型。请设置以下任一环境变量：\n" + \
                   "\n".join(f"  {p['env_key']}" for p in PROVIDERS.values() if p['env_key'])

        lines = [f"✅ 发现 {len(providers)} 个可用模型:"]
        for p in providers:
            key_preview = p["api_key"][:8] + "..." if p["api_key"] else ""
            lines.append(f"  {p['name']:<16} {p['models'][0]:<30} key={key_preview}")
        return "\n".join(lines)


# ── 快捷调用 ──
_default_pool = None


def get_pool() -> ModelPool:
    global _default_pool
    if _default_pool is None:
        _default_pool = ModelPool()
    return _default_pool


def llm_call(messages: list, system: str = "", max_tokens: int = 4096,
             temperature: float = 0.3) -> str:
    """快捷调模型（自动 failover）"""
    return get_pool().call(messages, system, max_tokens, temperature)
