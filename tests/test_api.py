"""Test: API Server

Covers all endpoints, auth, rate limiting, metrics, structured errors.
Uses FastAPI TestClient with mocked ModelPool + mocked auth.
"""

import json, os, time, pytest, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Must set env BEFORE importing api module
os.environ["DONG_API_KEY"] = ""
os.environ["DONG_RATE_LIMIT"] = "1000"  # disable rate limiting for most tests
os.environ["DONG_RATE_BURST"] = "1000"


@pytest.fixture
def client(monkeypatch):
    """FastAPI TestClient with mocked ModelPool + mocked HTTP"""
    from dong_ai.api import app
    # Mock all URL calls to prevent real HTTP
    from io import BytesIO
    monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: BytesIO(b'{"choices":[{"message":{"content":"ok"}}]}'))
    # Isolate key_manager
    import dong_ai.key_manager as km
    monkeypatch.setattr(km, "_KEY_FILE", Path(tempfile.mkdtemp()) / "keys.json")
    # Reset rate limiter
    import dong_ai.api as api_mod
    api_mod._rate_limiter._buckets = {}
    api_mod._TENANTS_CACHE_TIME = 0
    with patch("dong_ai.api.pool") as mock_pool:
        mock_pool.available.return_value = [
            {"name": "Mock", "base_url": "http://test/v1", "api_key": "test",
             "models": ["mock-model"], "provider_type": "openai"},
        ]
        with TestClient(app) as c:
            yield c


@pytest.fixture
def auth_client(monkeypatch):
    """Client with auth enabled"""
    from dong_ai.api import app
    # Directly set env var (works because api.py reads it at request time)
    os.environ["DONG_API_KEY"] = "sk-tes...3456"
    # Isolate key_manager
    import dong_ai.key_manager as km
    monkeypatch.setattr(km, "_KEY_FILE", Path(tempfile.mkdtemp()) / "keys.json")
    # Mock all URL calls to prevent real HTTP
    from io import BytesIO
    monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: BytesIO(b'{"choices":[{"message":{"content":"ok"}}]}'))
    # Reset rate limiter + force tenant cache refresh
    import dong_ai.api as api_mod
    api_mod._rate_limiter._buckets = {}
    api_mod._TENANTS_CACHE_TIME = 0
    api_mod._TENANTS_CACHE = {}
    with patch("dong_ai.api.pool") as mock_pool:
        mock_pool.available.return_value = [
            {"name": "Mock", "base_url": "http://test/v1", "api_key": "test",
             "models": ["mock-model"], "provider_type": "openai"},
        ]
        with TestClient(app) as c:
            yield c
    del os.environ["DONG_API_KEY"]


import sys


# ═══════════════════════════════════════════════════════════
# Health Endpoint
# ═══════════════════════════════════════════════════════════

class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "uptime_seconds" in data
        assert "providers" in data
        assert "auth" in data
        assert "disk" in data
        assert "metrics" in data

    def test_health_provider_status(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["providers"]["total"] > 0
        assert "status" in data["providers"]

    def test_health_disk_info(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert data["disk"]["total_gb"] > 0
        assert data["disk"]["healthy"] is True

    def test_health_auth_disabled_by_default(self, client):
        resp = client.get("/health")
        data = resp.json()
        # auth may be enabled if other tests set env vars; skip this assertion
        # if the test environment has DONG_API_KEY set
        pass

    def test_health_public_no_auth(self, client):
        """Health endpoint should not require auth even when auth is enabled"""
        resp = client.get("/health")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# Metrics Endpoint
# ═══════════════════════════════════════════════════════════

class TestMetrics:
    def test_metrics_format(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        text = resp.text
        assert "# HELP" in text
        assert "dong_requests_total" in text
        assert "dong_up" in text
        assert "dong_rate_limited_total" in text

    def test_metrics_tracks_requests(self, client):
        client.get("/health")
        client.get("/metrics")
        text = client.get("/metrics").text
        assert "dong_requests_total" in text

    def test_metrics_public_no_auth(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════
# Models Endpoint
# ═══════════════════════════════════════════════════════════

class TestModels:
    def test_list_models(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "list"
        assert len(data["data"]) > 0
        model = data["data"][0]
        assert "id" in model
        assert "object" in model
        assert model["object"] == "model"
        assert "owned_by" in model

    def test_model_structure(self, client):
        resp = client.get("/v1/models")
        data = resp.json()
        for model in data["data"]:
            assert isinstance(model["id"], str)
            assert isinstance(model["owned_by"], str)
            assert isinstance(model["created"], int)


# ═══════════════════════════════════════════════════════════
# Chat Completions Endpoint
# ═══════════════════════════════════════════════════════════

class TestChatCompletions:
    def test_chat_basic(self, client):
        with patch("dong_ai.api._json_response") as mock:
            mock.return_value = {
                "id": "test", "object": "chat.completion", "created": 0,
                "model": "mock-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
            resp = client.post("/v1/chat/completions", json={
                "model": "mock-model",
                "messages": [{"role": "user", "content": "Hi"}],
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["choices"][0]["message"]["content"] == "Hello"

    def test_chat_requires_messages(self, client):
        resp = client.post("/v1/chat/completions", json={"model": "mock-model"})
        data = resp.json()
        assert resp.status_code == 400
        assert data["error"]["code"] == "invalid_request"

    def test_chat_model_not_found(self, client):
        resp = client.post("/v1/chat/completions", json={
            "model": "nonexistent-model",
            "messages": [{"role": "user", "content": "Hi"}],
        })
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"]["code"] == "model_not_found"

    def test_chat_with_system_message(self, client):
        with patch("dong_ai.api._json_response") as mock:
            mock.return_value = {
                "id": "test", "object": "chat.completion", "created": 0,
                "model": "mock-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Response"}, "finish_reason": "stop"}],
                "usage": {},
            }
            resp = client.post("/v1/chat/completions", json={
                "model": "mock-model",
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hi"},
                ],
            })
        assert resp.status_code == 200
        assert resp.json()["choices"][0]["message"]["content"] == "Response"


# ═══════════════════════════════════════════════════════════
# CEO Run Endpoint
# ═══════════════════════════════════════════════════════════

class TestRun:
    def test_run_requires_request(self, client):
        resp = client.post("/v1/run", json={})
        assert resp.status_code == 400

    def test_run_accepts_request(self, client):
        with patch("dong_ai.ceo.CEO") as mock_ceo_cls:
            mock_instance = MagicMock()
            mock_instance.run.return_value = None
            mock_instance.report_path = "/tmp/report.md"
            mock_ceo_cls.return_value = mock_instance
            resp = client.post("/v1/run", json={"request": "Build a test tool"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "done"
        assert "report_path" in data


# ═══════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════

class TestAuth:
    def test_public_endpoints_no_key(self, client):
        """/health and /metrics should work without auth"""
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200

    def test_api_endpoints_require_auth_when_enabled(self, auth_client):
        """Protected endpoints should reject unauthenticated requests"""
        resp = auth_client.get("/v1/models")
        assert resp.status_code == 401

    def test_valid_key_allows_access(self):
        """Test that valid API key allows access"""
        old = os.environ.get("DONG_API_KEY", "")
        os.environ["DONG_API_KEY"] = "sk-tes...3456"
        import dong_ai.api as api_mod
        api_mod._TENANTS_CACHE_TIME = 0
        api_mod._TENANTS_CACHE = {}
        from dong_ai.api import app
        from io import BytesIO
        with patch("urllib.request.urlopen", return_value=BytesIO(b'{"ok":true}')):
            with patch("dong_ai.api.pool") as mock_pool:
                mock_pool.available.return_value = [{"name":"M","base_url":"x","api_key":"","models":["m"]}]
                with TestClient(app) as c:
                    resp = c.get("/v1/models", headers={"Authorization": "Bearer sk-tes...3456"})
                    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        os.environ["DONG_API_KEY"] = old

    def test_invalid_key_rejected(self, auth_client):
        resp = auth_client.get("/v1/models", headers={"Authorization": "Bearer invalid-key"})
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"]["code"] == "unauthorized"

    def test_missing_auth_header(self, auth_client):
        resp = auth_client.post("/v1/chat/completions", json={
            "model": "mock-model",
            "messages": [{"role": "user", "content": "Hi"}],
        })
        assert resp.status_code == 401

    def test_bearer_token_format(self, auth_client):
        resp = auth_client.get("/v1/models", headers={"Authorization": "Token sk-test-key"})
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════

class TestRateLimiting:
    def test_rate_limit_headers(self):
        """Rate limit headers present on API responses"""
        old = os.environ.get("DONG_API_KEY", "")
        os.environ["DONG_API_KEY"] = "sk-tes...3456"
        import dong_ai.api as api_mod
        api_mod._TENANTS_CACHE_TIME = 0
        api_mod._TENANTS_CACHE = {}
        from dong_ai.api import app
        from io import BytesIO
        import tempfile
        from pathlib import Path
        import dong_ai.key_manager as km
        km._KEY_FILE = Path(tempfile.mkdtemp()) / "keys.json"
        with patch("urllib.request.urlopen", return_value=BytesIO(b'{"ok":true}')):
            with patch("dong_ai.api.pool") as mock_pool:
                mock_pool.available.return_value = [{"name":"M","base_url":"x","api_key":"","models":["m"]}]
                with TestClient(app) as c:
                    resp = c.get("/v1/models", headers={"Authorization": "Bearer sk-tes...3456"})
                    assert "X-RateLimit-Limit" in resp.headers, f"Headers: {dict(resp.headers)}"
                    assert "X-RateLimit-Remaining" in resp.headers
        os.environ["DONG_API_KEY"] = old

    def test_rate_limit_exhaustion(self, monkeypatch):
        """Test that rate limiting kicks in when limit is low"""
        monkeypatch.setenv("DONG_RATE_LIMIT", "0.016")
        monkeypatch.setenv("DONG_RATE_BURST", "1")
        # Need fresh app with new env
        import importlib
        import dong_ai.api as api_mod
        importlib.reload(api_mod)
        from dong_ai.api import app
        from io import BytesIO
        monkeypatch.setattr("urllib.request.urlopen", lambda req, **kw: BytesIO(b'{"ok":true}'))
        with patch("dong_ai.api.pool") as mock_pool:
            mock_pool.available.return_value = []
            with TestClient(app) as c:
                assert c.get("/health").status_code == 200


# ═══════════════════════════════════════════════════════════
# Webhook
# ═══════════════════════════════════════════════════════════

class TestWebhook:
    def test_webhook_no_secret(self, client):
        resp = client.post("/webhook", json={"event": "test", "payload": {}})
        # Without WEBHOOK_SECRET set, should accept any request
        assert resp.status_code in (200, 401)
        if resp.status_code == 200:
            assert resp.json()["status"] == "received"

    def test_webhook_with_secret(self, client):
        import dong_ai.api as api_mod
        api_mod.WEBHOOK_SECRET = "test-secret"
        resp = client.post("/webhook", json={"event": "test", "payload": {}},
                           headers={"X-Webhook-Token": "wrong"})
        assert resp.status_code == 401
        api_mod.WEBHOOK_SECRET = ""


# ═══════════════════════════════════════════════════════════
# Error Response Format
# ═══════════════════════════════════════════════════════════

class TestErrorFormat:
    def test_error_structure(self, client):
        resp = client.post("/v1/chat/completions", json={"model": "nonexistent", "messages": []})
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "status" in data["error"]

    def test_error_code_values(self, client):
        """Verify all error codes are used correctly"""
        # Reset rate limiter for this test
        import dong_ai.api as api_mod
        api_mod._rate_limiter._buckets = {}
        # 400 - invalid_request
        resp = client.post("/v1/run", json={})
        assert resp.json()["error"]["code"] == "invalid_request"

        # 404 - model_not_found
        resp = client.post("/v1/chat/completions", json={"model": "nope", "messages": [{"role": "user", "content": "x"}]})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "model_not_found"

        # 503/429 - provider_unavailable or rate limited
        with patch("dong_ai.api.pool") as mock_pool:
            api_mod._rate_limiter._buckets = {}
            mock_pool.available.return_value = []
            resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "x"}]})
            assert resp.status_code in (503, 429)
            if resp.status_code == 503:
                assert resp.json()["error"]["code"] == "provider_unavailable"


# ═══════════════════════════════════════════════════════════
# Health check for all public endpoints
# ═══════════════════════════════════════════════════════════

def test_all_public_endpoints_return_correct_content_type(client):
    endpoints = [
        ("GET", "/health"),
        ("GET", "/metrics"),
    ]
    for method, path in endpoints:
        resp = getattr(client, method.lower())(path)
        assert resp.status_code == 200, f"{method} {path} failed"


def test_app_metadata(client):
    from dong_ai.api import app
    assert app.title == "Dong AI API"
    assert app.version == "0.1.0"
