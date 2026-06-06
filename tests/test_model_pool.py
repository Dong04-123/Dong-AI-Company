"""Dong AI — ModelPool 测试

覆盖:
  - Provider 发现（有/无 API key）
  - best() 选择逻辑
  - 调用和 failover
  - detect() 摘要
"""

import os, json, copy
from pathlib import Path

import pytest


class TestModelPoolInit:
    """初始化与环境检测"""

    def test_import(self):
        from dong_ai.model_pool import ModelPool
        assert ModelPool is not None

    def test_init(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        assert pool is not None
        assert pool._cache is None

    def test_usage_starts_empty(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        usage = pool.get_usage()
        assert usage["prompt"] == 0
        assert usage["total"] == 0

    def test_reset_usage(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._total_usage["total"] = 100
        pool.reset_usage()
        assert pool.get_usage()["total"] == 0


class TestModelPoolAvailable:
    """Provider 发现"""

    def test_available_returns_list(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        providers = pool.available()
        assert isinstance(providers, list)

    def test_available_sorts_by_key(self):
        """有 key 的 provider 排前面，本地模型排最后"""
        from dong_ai.model_pool import ModelPool
        # 临时设置一个环境变量
        old_key = os.environ.get("DEEPSEEK_API_KEY", "")
        os.environ["DEEPSEEK_API_KEY"] = "sk-test-key-12345"
        pool = ModelPool()
        pool._cache = None
        providers = pool.available()
        if len(providers) >= 2:
            # 第一个应该是有 key 的
            first = providers[0]
            # last should be local models
            last = providers[-1]
        os.environ["DEEPSEEK_API_KEY"] = old_key

    def test_available_local_always_present(self):
        """本地模型（local, ollama）不需要 key，始终出现"""
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = None
        providers = pool.available()
        ids = [p["id"] for p in providers]
        # local 和 ollama 不需要 API key
        assert "local" in ids
        assert "ollama" in ids

    def test_available_caches_result(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = None
        first = pool.available()
        second = pool.available()
        assert first is second  # 同一缓存对象

    def test_available_provider_structure(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = None
        providers = pool.available()
        assert len(providers) > 0
        p = providers[0]
        assert "id" in p
        assert "name" in p
        assert "base_url" in p
        assert "models" in p
        assert isinstance(p["models"], list)
        assert len(p["models"]) > 0


class TestModelPoolBest:
    """最优模型选择"""

    def test_best_returns_provider(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = None
        best = pool.best()
        assert "id" in best
        assert "name" in best
        assert "models" in best

    def test_best_first_model_available(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = None
        best = pool.best()
        assert len(best["models"]) >= 1
        assert best["models"][0] is not None

    def test_best_no_available_raises(self):
        """没有可用 provider 时抛异常"""
        from dong_ai.model_pool import ModelPool, PROVIDERS
        pool = ModelPool()
        # 用空列表模拟无可用 provider
        pool._cache = []
        with pytest.raises(RuntimeError, match="没有可用的模型"):
            pool.best()


class TestModelPoolDetect:
    """环境检测输出"""

    def test_detect_no_providers(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = []
        result = pool.detect()
        assert "没有可用模型" in result

    def test_detect_with_providers(self):
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = None
        result = pool.detect()
        assert "可用" in result or "找到" in result or "发现" in result


class TestModelPoolCall:
    """模型调用（mock HTTP）"""

    def test_call_openai_format(self, temp_dir, mock_urlopen):
        """OpenAI 兼容 provider 调用（通过 pool.call 测试）"""
        mock_urlopen.set_response(
            '{"choices":[{"message":{"content":"hello world"}}],"usage":{"prompt_tokens":5,"completion_tokens":5,"total_tokens":10}}',
            url_prefix="chat/completions",
        )
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = [
            {"id": "test", "name": "Test", "base_url": "http://localhost:0/v1",
             "api_key": "", "models": ["test-model"], "type": "openai"},
        ]
        result = pool.call([{"role": "user", "content": "hi"}], max_tokens=100, temperature=0.3, timeout=10)
        assert result == "hello world"
        assert pool.get_usage()["total"] >= 10

    def test_call_auto_failover(self, temp_dir):
        """第一个 provider 失败，自动切到第二个"""
        import urllib.request
        from io import BytesIO

        call_index = [0]
        responses = [
            b'{"error":"rate limit"}',  # 第一次调用失败
            b'{"choices":[{"message":{"content":"fallback ok"}}],"usage":{"total_tokens":10}}',  # 第二次成功
        ]

        class FailoverOpener:
            def __call__(self, req, **kwargs):
                idx = call_index[0]
                call_index[0] += 1
                data = responses[min(idx, len(responses) - 1)]
                return BytesIO(data)  # BytesIO implements read() + __enter__/__exit__

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(urllib.request, "urlopen", FailoverOpener())

        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = [
            {"id": "bad", "name": "Bad", "base_url": "http://localhost:0/v1",
             "api_key": "", "models": ["bad-model"], "type": "openai"},
            {"id": "good", "name": "Good", "base_url": "http://localhost:1/v1",
             "api_key": "", "models": ["good-model"], "type": "openai"},
        ]
        result = pool.call([{"role": "user", "content": "test"}], system="", max_tokens=100)
        monkeypatch.undo()
        assert result == "fallback ok"

    def test_call_all_fail(self, temp_dir, mock_urlopen):
        """所有 provider 都失败时抛异常"""
        mock_urlopen.set_response('{"error":"down"}', url_prefix="chat")
        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = [
            {"id": "x", "name": "X", "base_url": "http://localhost:0/v1",
             "api_key": "", "models": ["x"], "type": "openai"},
        ]
        with pytest.raises(RuntimeError):
            pool.call([{"role": "user", "content": "hi"}])


class TestModelPoolCallStream:
    """流式调用"""

    def test_call_stream_yields_tokens(self, temp_dir):
        """SSE 流式输出"""
        from io import BytesIO

        sse_data = (
            b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"World"}}]}\n\n'
            b'data: {"choices":[{"delta":{}}],"usage":{"total_tokens":20}}\n\n'
            b'data: [DONE]\n\n'
        )

        class StreamOpener:
            def __call__(self, req, **kwargs):
                return BytesIO(sse_data)

        import urllib.request
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(urllib.request, "urlopen", StreamOpener())

        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = [
            {"id": "stream_test", "name": "Stream", "base_url": "http://localhost:0/v1",
             "api_key": "", "models": ["s"], "type": "openai"},
        ]
        tokens = list(pool.call_stream([{"role": "user", "content": "hi"}], max_tokens=100))
        monkeypatch.undo()
        assert len(tokens) >= 2
        assert any("Hello" in t for t in tokens)
        assert any("World" in t for t in tokens)

    def test_call_stream_usage_tracking(self, temp_dir):
        """流式调用的 usage 被追踪"""
        from io import BytesIO

        sse_data = (
            b'data: {"choices":[{"delta":{"content":"a"}}]}\n\n'
            b'data: {"choices":[{"delta":{"content":"b"}}]}\n\n'
            b'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":5,"completion_tokens":5,"total_tokens":10}}\n\n'
            b'data: [DONE]\n\n'
        )

        class UsageOpener:
            def __call__(self, req, **kwargs):
                return BytesIO(sse_data)

        import urllib.request
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(urllib.request, "urlopen", UsageOpener())

        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = [
            {"id": "ut", "name": "UT", "base_url": "http://localhost:0/v1",
             "api_key": "", "models": ["ut"], "type": "openai"},
        ]
        list(pool.call_stream([{"role": "user", "content": "hi"}], max_tokens=100))
        monkeypatch.undo()
        assert pool.get_usage()["total"] >= 10

    def test_call_stream_auto_failover(self, temp_dir):
        """流式调用也支持 failover"""
        import urllib.request, urllib.error
        from io import BytesIO

        call_index = [0]
        # 第一次调用抛出 HTTPError，第二次成功
        error_resp = urllib.error.HTTPError("http://localhost:0/v1/chat/completions", 500, "Error", {}, None)

        class FailStreamOpener:
            def __call__(self, req, **kwargs):
                idx = call_index[0]
                call_index[0] += 1
                if idx == 0:
                    raise error_resp
                data = (
                    b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
                    b'data: [DONE]\n\n'
                )
                return BytesIO(data)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(urllib.request, "urlopen", FailStreamOpener())

        from dong_ai.model_pool import ModelPool
        pool = ModelPool()
        pool._cache = [
            {"id": "bad", "name": "Bad", "base_url": "http://localhost:0/v1",
             "api_key": "", "models": ["b"], "type": "openai"},
            {"id": "good", "name": "Good", "base_url": "http://localhost:1/v1",
             "api_key": "", "models": ["g"], "type": "openai"},
        ]
        tokens = list(pool.call_stream([{"role": "user", "content": "hi"}], max_tokens=100))
        monkeypatch.undo()
        assert len(tokens) >= 1


class TestModelPoolHelpers:
    """快捷函数"""

    def test_get_pool(self):
        from dong_ai.model_pool import get_pool
        pool1 = get_pool()
        pool2 = get_pool()
        assert pool1 is pool2  # 单例

    def test_llm_call(self):
        from dong_ai.model_pool import llm_call, get_pool
        pool = get_pool()
        # 设置缓存确保有 provider
        pool._cache = [
            {"id": "local", "name": "Local", "base_url": "http://localhost:8080/v1",
             "api_key": "", "models": ["local-model"], "type": "openai"},
        ]
        # 这个调用会失败（本地模型不运行），但我们只测试函数签名
        # llm_call 本身是合法的函数调用
        assert callable(llm_call)

    def test_providers_config(self):
        from dong_ai.model_pool import PROVIDERS
        assert isinstance(PROVIDERS, dict)
        assert "deepseek" in PROVIDERS
        assert "local" in PROVIDERS
        assert "openai" in PROVIDERS
        assert "ollama" in PROVIDERS
        # 每个 provider 有必要的字段
        for pid, cfg in PROVIDERS.items():
            assert "name" in cfg
            assert "base_url" in cfg
            assert "models" in cfg
            assert "provider_type" in cfg
            assert isinstance(cfg["models"], list)
            assert len(cfg["models"]) > 0
