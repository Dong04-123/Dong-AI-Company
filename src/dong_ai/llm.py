"""Dong AI — LLM 客户端接口

统一 HTTP + SSE 实现，所有 LLM 调用通过此接口。
model_pool 的 call()/call_stream() 委托给此模块。

用法:
  from llm import LLMConfig, OpenAICompatibleClient, create_client
  config = LLMConfig(model="deepseek-chat", base_url="...", api_key="...")
  client = OpenAICompatibleClient(config)
  resp = client.chat([{"role":"user","content":"你好"}])
  json_resp = client.chat_json(messages, system="输出 JSON")
  for token in client.chat_stream(messages):
      print(token)
"""
from __future__ import annotations

import json, os, urllib.request
from typing import Generator
from dataclasses import dataclass


@dataclass
class LLMConfig:
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7
    timeout: int = 120


class LLMResponse:
    """结构化 LLM 响应"""
    def __init__(self, text: str, usage: dict = None) -> None:
        self.text = text
        self.usage = usage or {"prompt": 0, "completion": 0, "total": 0}

    def json(self) -> dict:
        import re
        m = re.search(r'```(?:json)?\s*\n(.*?)\n```', self.text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        return json.loads(self.text)


class LLMClient:
    """LLM 客户端接口——所有 LLM 调用通过此接口"""
    def __init__(self, config: LLMConfig = None) -> None:
        self.config = config or LLMConfig()
        self._usage_total = {"prompt": 0, "completion": 0, "total": 0}

    def chat(self, messages: list, system: str = "", **kwargs) -> LLMResponse:
        raise NotImplementedError

    def chat_stream(self, messages: list, system: str = "", **kwargs) -> Generator[str, None, None]:
        raise NotImplementedError

    def chat_json(self, messages: list, system: str = "", **kwargs) -> dict:
        resp = self.chat(messages, system, **kwargs)
        return resp.json()

    @property
    def usage(self) -> dict:
        return dict(self._usage_total)


class OpenAICompatibleClient(LLMClient):
    """OpenAI 兼容 API 实现"""

    HEADERS = {"Content-Type": "application/json"}

    def _build_payload(self, messages: list, system: str, stream: bool, **kwargs) -> dict:
        cfg = {**vars(self.config), **kwargs}
        payload = {
            "model": cfg["model"],
            "messages": ([{"role": "system", "content": system}] + messages if system else messages),
            "max_tokens": cfg.get("max_tokens", 8192),
            "temperature": cfg.get("temperature", 0.7),
            "stream": stream,
        }
        if kwargs:
            payload.update(kwargs)
        return payload

    def _request(self, payload: dict, stream: bool = False):
        headers = dict(self.HEADERS)
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        req = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers=headers, method="POST")
        return urllib.request.urlopen(req, timeout=self.config.timeout)

    def chat(self, messages: list, system: str = "", **kwargs) -> LLMResponse:
        payload = self._build_payload(messages, system, stream=False, **kwargs)
        with self._request(payload) as resp:
            data = json.loads(resp.read())
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        u = {"prompt": usage.get("prompt_tokens", 0),
             "completion": usage.get("completion_tokens", 0),
             "total": usage.get("total_tokens", 0)}
        for k in u: self._usage_total[k] += u[k]
        return LLMResponse(choice, u)

    def chat_stream(self, messages: list, system: str = "", **kwargs) -> Generator[str, None, None]:
        payload = self._build_payload(messages, system, stream=True, **kwargs)
        payload["stream"] = True
        with self._request(payload) as resp:
            buffer = ""
            for chunk in resp:
                buffer += chunk.decode("utf-8", errors="replace")
                if not buffer.endswith("\n"):
                    continue
                line = buffer.strip()
                buffer = ""
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            yield content
                        if data.get("usage"):
                            u = data["usage"]
                            self._usage_total["prompt"] += u.get("prompt_tokens", 0)
                            self._usage_total["completion"] += u.get("completion_tokens", 0)
                            self._usage_total["total"] += u.get("total_tokens", 0)
                    except json.JSONDecodeError:
                        pass


# ── 工厂 ──

def create_client(config: LLMConfig = None) -> LLMClient:
    """创建 LLM 客户端。

    可以传入 LLMConfig，不传时返回默认空配置客户端。
    自动发现请使用 ModelPool（在 model_pool 模块中）。
    """
    if config is None:
        config = LLMConfig()
    return OpenAICompatibleClient(config)
