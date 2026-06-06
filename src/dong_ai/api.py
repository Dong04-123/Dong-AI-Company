"""Dong AI — FastAPI API Server (A-grade production)

企业特性:
  - API Key 认证 (Bearer Token)
  - 动态 Key 管理 (dong key create/list/revoke)
  - 多租户隔离 (DONG_API_KEYS JSON)
  - Token Bucket 速率限制 (每 Key + 端点)
  - 结构化错误响应 (RFC 7807 Problem Details)
  - 深度健康检查 (Provider ping + 磁盘 + 资源)
  - Prometheus /metrics
  - 结构化请求日志
  - 优雅关闭 (SIGTERM)
  - OpenAPI 文档 (/docs)

启动:
  dong serve --port 8648
  DONG_API_KEY=sk-xxx dong serve    # 启用认证
"""
from __future__ import annotations

import json, time, uuid, os, threading, re, asyncio, signal
from typing import Optional
from datetime import datetime, timezone

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path
except ImportError:
    raise ImportError("需要安装 fastapi: pip install 'dong-ai[server]'")

from dong_ai.model_pool import ModelPool


# ═══════════════════════════════════════════════════════════
# Auth — 动态 Key 管理
# ═══════════════════════════════════════════════════════════

from dong_ai.key_manager import resolve_tenants, verify_key, _key_fingerprint

_TENANTS_CACHE = resolve_tenants()
_TENANTS_CACHE_TIME = time.time()
_TENANTS_CACHE_TTL = 30  # 每 30 秒重载


def _refresh_tenants() -> None:
    """热刷新租户映射"""
    global _TENANTS_CACHE, _TENANTS_CACHE_TIME
    now = time.time()
    if now - _TENANTS_CACHE_TIME > _TENANTS_CACHE_TTL:
        _TENANTS_CACHE = resolve_tenants()
        _TENANTS_CACHE_TIME = now


def _get_tenant(request: Request) -> Optional[str]:
    """从请求中提取租户 ID（支持静态 env key + 动态持久化 key）"""
    _refresh_tenants()
    auth = request.headers.get("Authorization", "")
    m = re.match(r"^Bearer\s+(.+)$", auth)
    if m:
        key = m.group(1)
        # 1. 先查缓存
        tenant = _TENANTS_CACHE.get(key)
        if tenant:
            request.state.key_fingerprint = _key_fingerprint(key)
            return tenant
        # 2. 回退到持久化验证（新创建的 key 可能还没进缓存）
        tenant = verify_key(key)
        if tenant:
            _TENANTS_CACHE[key] = tenant
            request.state.key_fingerprint = _key_fingerprint(key)
            return tenant
    return None


# ═══════════════════════════════════════════════════════════
# Rate Limiting
# ═══════════════════════════════════════════════════════════

from dong_ai.rate_limiter import RateLimiter

_rate_limiter = RateLimiter()


# ═══════════════════════════════════════════════════════════
# 结构化错误响应 (RFC 7807 Problem Details)
# ═══════════════════════════════════════════════════════════

class ErrorCode:
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    MODEL_NOT_FOUND = "model_not_found"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_REQUEST = "invalid_request"
    UPSTREAM_ERROR = "upstream_error"
    INTERNAL_ERROR = "internal_error"
    WEBHOOK_INVALID = "webhook_invalid"


def _error_response(status: int, code: str, detail: str, extra: dict = None) -> JSONResponse:
    """RFC 7807 Problem Details JSON"""
    body = {
        "error": {
            "code": code,
            "message": detail,
            "status": status,
        }
    }
    if extra:
        body["error"].update(extra)
    return JSONResponse(status_code=status, content=body)


# ═══════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════

class Metrics:
    """进程内 Prometheus 指标收集"""
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._requests_total = 0
        self._requests_by_endpoint = {}
        self._requests_by_tenant = {}
        self._requests_by_status = {}
        self._latency_buckets = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        self._latency_count = {b: 0 for b in self._latency_buckets}
        self._errors_total = 0
        self._errors_by_code = {}
        self._tokens_total = 0
        self._rate_limited_total = 0
        self._start_time = time.time()

    def inc_request(self, endpoint: str, tenant: str = "anonymous") -> None:
        with self.lock:
            self._requests_total += 1
            self._requests_by_endpoint[endpoint] = self._requests_by_endpoint.get(endpoint, 0) + 1
            self._requests_by_tenant[tenant] = self._requests_by_tenant.get(tenant, 0) + 1

    def inc_status(self, code: int) -> None:
        with self.lock:
            bucket = f"{code // 100}xx"
            self._requests_by_status[bucket] = self._requests_by_status.get(bucket, 0) + 1

    def record_latency(self, seconds: float) -> None:
        with self.lock:
            for b in self._latency_buckets:
                if seconds <= b:
                    self._latency_count[b] = self._latency_count.get(b, 0) + 1
                    break
            else:
                self._latency_count["+inf"] = self._latency_count.get("+inf", 0) + 1

    def inc_error(self, code: str = "unknown") -> None:
        with self.lock:
            self._errors_total += 1
            self._errors_by_code[code] = self._errors_by_code.get(code, 0) + 1

    def inc_rate_limited(self) -> None:
        with self.lock:
            self._rate_limited_total += 1

    def add_tokens(self, n: int) -> None:
        with self.lock:
            self._tokens_total += n

    def snapshot(self) -> str:
        with self.lock:
            up = int(time.time() - self._start_time)
            lines = [
                "# HELP dong_requests_total Total requests",
                "# TYPE dong_requests_total counter",
                f'dong_requests_total {self._requests_total}',
                "",
                "# HELP dong_requests_by_endpoint Requests per endpoint",
                "# TYPE dong_requests_by_endpoint counter",
            ]
            for ep, count in sorted(self._requests_by_endpoint.items()):
                lines.append(f'dong_requests_by_endpoint{{endpoint="{ep}"}} {count}')
            lines.extend(["", "# HELP dong_requests_by_tenant Requests per tenant", "# TYPE dong_requests_by_tenant counter"])
            for t, count in sorted(self._requests_by_tenant.items()):
                lines.append(f'dong_requests_by_tenant{{tenant="{t}"}} {count}')
            lines.extend(["", "# HELP dong_requests_by_status Requests per status class", "# TYPE dong_requests_by_status counter"])
            for bucket, count in sorted(self._requests_by_status.items()):
                lines.append(f'dong_requests_by_status{{status="{bucket}"}} {count}')
            lines.extend(["", "# HELP dong_errors_total Total errors by code", "# TYPE dong_errors_total counter"])
            for code, count in sorted(self._errors_by_code.items()):
                lines.append(f'dong_errors_total{{code="{code}"}} {count}')
            lines.extend(["", "# HELP dong_rate_limited_total Total rate-limited requests", "# TYPE dong_rate_limited_total counter", f'dong_rate_limited_total {self._rate_limited_total}'])
            lines.extend(["", "# HELP dong_tokens_total Total tokens generated", "# TYPE dong_tokens_total counter", f'dong_tokens_total {self._tokens_total}'])
            lines.extend(["", "# HELP dong_up Server uptime seconds", "# TYPE dong_up gauge", f'dong_up {up}'])
            return "\n".join(lines) + "\n"


_metrics = Metrics()


# ═══════════════════════════════════════════════════════════
# App
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="Dong AI API",
    version="0.1.0",
    description="OpenAI-compatible API with enterprise features: tenant isolation, rate limiting, Prometheus metrics, structured logging, and deep health checks.",
    contact={"name": "Dong AI", "url": "https://github.com/Dong04-123/Dong-AI-Company"},
    license_info={"name": "MIT", "url": "https://github.com/Dong04-123/Dong-AI-Company/blob/main/LICENSE"},
)

# CORS — 生产环境建议收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("DONG_CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pool = ModelPool()


# ═══════════════════════════════════════════════════════════
# 中间件栈（执行顺序：Metrics → RateLimit → Auth → Handler）
# ═══════════════════════════════════════════════════════════

@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    """请求指标 — 第一个执行，确保所有请求都被计数"""
    endpoint = request.url.path
    tenant = getattr(request.state, "tenant", "anonymous")
    start = time.time()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as e:
        _metrics.inc_error("unhandled")
        raise
    elapsed = time.time() - start
    _metrics.inc_request(endpoint, tenant)
    _metrics.inc_status(status)
    _metrics.record_latency(elapsed)
    return response


@app.middleware("http")
async def _rate_limit_middleware(request: Request, call_next):
    """速率限制 — 公共端点不限，API 端点按 tenant+endpoint 限"""
    public_paths = ["/health", "/metrics", "/", "/docs", "/openapi.json", "/redoc"]
    if request.url.path in public_paths or request.method == "OPTIONS":
        return await call_next(request)

    tenant = getattr(request.state, "tenant", "anonymous")
    allowed, wait = _rate_limiter.check(tenant, request.url.path)
    if not allowed:
        _metrics.inc_rate_limited()
        retry_after = max(1, int(wait) + 1)
        resp = _error_response(
            429, "rate_limited",
            f"Rate limit exceeded. Retry after {retry_after}s",
            {"retry_after_seconds": retry_after},
        )
        resp.headers["Retry-After"] = str(retry_after)
        resp.headers["X-RateLimit-Limit"] = str(int(_rate_limiter._rate * 60))
        resp.headers["X-RateLimit-Remaining"] = "0"
        resp.headers["X-RateLimit-Reset"] = str(int(time.time() + wait))
        from dong_ai.logger import get_logger
        get_logger("api").warn("rate_limited", tenant=tenant, endpoint=request.url.path)
        return resp

    return await call_next(request)


@app.middleware("http")
async def _auth_middleware(request: Request, call_next):
    """API Key 认证"""
    public_paths = ["/health", "/metrics", "/", "/docs", "/openapi.json", "/redoc"]
    if request.url.path in public_paths or request.method == "OPTIONS":
        return await call_next(request)

    has_auth = bool(os.environ.get("DONG_API_KEY") or resolve_tenants())
    if has_auth:
        tenant = _get_tenant(request)
        if tenant is None:
            return _error_response(401, "unauthorized", "Valid API Key required")
        request.state.tenant = tenant
    else:
        request.state.tenant = "anonymous"

    response = await call_next(request)
    # 附加速率限制头部
    try:
        tenant = getattr(request.state, "tenant", "anonymous")
        remaining = _rate_limiter.get_remaining(tenant, request.url.path)
        limit = int(os.environ.get("DONG_RATE_LIMIT", "60"))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    except Exception:
        pass
    return response


# ═══════════════════════════════════════════════════════════
# 健康状况
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health() -> dict:
    """深度健康检查 — 返回系统各组件状态"""
    from dong_ai.key_manager import list_keys

    providers = pool.available()
    # 检测各 provider 可用性（快速 ping）
    provider_status = {}
    for p in providers[:10]:
        try:
            from dong_ai.llm import LLMConfig, OpenAICompatibleClient
            client = OpenAICompatibleClient(LLMConfig(
                model=p["models"][0], base_url=p["base_url"],
                api_key=p.get("api_key", ""), max_tokens=1, temperature=0,
            ))
            start = time.time()
            resp = client.chat([{"role": "user", "content": "hi"}])
            elapsed = time.time() - start
            provider_status[p["name"]] = {"status": "ok", "latency_ms": int(elapsed * 1000)}
        except Exception as e:
            provider_status[p["name"]] = {"status": "error", "error": str(e)[:60]}

    # 磁盘检查
    import shutil
    disk = shutil.disk_usage(Path.home())
    disk_ok = disk.free / disk.total > 0.05  # 至少 5% 空闲

    # Key 统计
    try:
        active_keys = len([k for k in list_keys() if not k["revoked"]])
    except Exception:
        active_keys = 0

    return {
        "status": "ok",
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - _metrics._start_time),
        "auth": {
            "enabled": bool(os.environ.get("DONG_API_KEY") or resolve_tenants()),
            "active_keys": active_keys,
            "rate_limit": int(float(os.environ.get("DONG_RATE_LIMIT", "60"))),
        },
        "providers": {
            "total": len(providers),
            "available": sum(1 for s in provider_status.values() if s["status"] == "ok"),
            "status": provider_status,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "healthy": disk_ok,
        },
        "metrics": {
            "total_requests": _metrics._requests_total,
            "total_errors": _metrics._errors_total,
            "rate_limited": _metrics._rate_limited_total,
            "tokens_generated": _metrics._tokens_total,
        },
    }


# ═══════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════

@app.get("/metrics")
async def metrics() -> str:
    """Prometheus 格式指标"""
    return _metrics.snapshot()


# ═══════════════════════════════════════════════════════════
# Models (OpenAI 兼容)
# ═══════════════════════════════════════════════════════════

@app.get("/v1/models", response_model=dict)
async def list_models(request: Request) -> dict:
    """OpenAI 兼容 — 列出可用模型"""
    providers = pool.available()
    models = []
    for p in providers:
        for model_id in p["models"]:
            models.append({
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": p.get("name", "unknown"),
            })
    return {"object": "list", "data": models}


# ═══════════════════════════════════════════════════════════
# Chat Completions (OpenAI 兼容)
# ═══════════════════════════════════════════════════════════

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容的聊天补全（支持流式和非流式）"""
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "")
    stream = body.get("stream", False)
    max_tokens = body.get("max_tokens", 8192)
    temperature = body.get("temperature", 0.7)

    # 校验
    if not messages:
        return _error_response(400, "invalid_request", "messages is required")

    # 提取 system prompt
    system = ""
    filtered = []
    for m in messages:
        if m.get("role") == "system":
            system = m["content"]
        elif m.get("role") in ("user", "assistant"):
            filtered.append(m)
    messages = filtered

    # 日志
    tenant = getattr(request.state, "tenant", "anonymous")
    _log_request(tenant, "chat_completions", model, len(messages))

    # 选择 provider
    providers = pool.available()
    if model:
        target = next((p for p in providers if model in p["models"]), None)
        if not target:
            return _error_response(404, "model_not_found", f"Model '{model}' not found", {"available_models": [m for p in providers for m in p["models"]]})
        providers = [target]

    if not providers:
        return _error_response(503, "provider_unavailable", "No configured model providers available")

    if stream:
        return _stream_response(providers[0], messages, system, max_tokens, temperature, model)
    else:
        return _json_response(providers[0], messages, system, max_tokens, temperature, model)


def _json_response(provider, messages, system, max_tokens, temperature, model_id) -> dict:
    """非流式响应"""
    from dong_ai.llm import LLMConfig, OpenAICompatibleClient
    model = model_id or provider["models"][0]

    client = OpenAICompatibleClient(LLMConfig(
        model=model, base_url=provider["base_url"],
        api_key=provider.get("api_key", ""),
        max_tokens=max_tokens, temperature=temperature,
    ))

    try:
        resp = client.chat(messages, system=system if system else None)
    except Exception as e:
        _metrics.inc_error("upstream_error")
        return _error_response(502, "upstream_error", f"{provider.get('name', 'provider')} error: {str(e)[:200]}")

    _metrics.add_tokens(resp.usage.get("total_tokens", 0) if resp.usage else 0)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": resp.text},
            "finish_reason": "stop",
        }],
        "usage": resp.usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _stream_response(provider, messages, system, max_tokens, temperature, model_id):
    """流式 SSE 响应"""
    from dong_ai.llm import LLMConfig, OpenAICompatibleClient
    model = model_id or provider["models"][0]

    client = OpenAICompatibleClient(LLMConfig(
        model=model, base_url=provider["base_url"],
        api_key=provider.get("api_key", ""),
        max_tokens=max_tokens, temperature=temperature,
    ))

    response_start = time.time()

    async def generate():
        nonlocal response_start
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"

        token_count = 0
        try:
            for token in client.chat_stream(messages, system=system if system else "", max_tokens=max_tokens, temperature=temperature):
                token_count += 1
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {'content': token}, 'finish_reason': None}]})}\n\n"

            _metrics.add_tokens(token_count)
            yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
        except Exception as e:
            _metrics.inc_error("stream_error")
            yield f"data: {json.dumps({'error': {'message': f'Stream error: {str(e)[:100]}'}})}\n\n"

        yield "data: [DONE]\n\n"
        _metrics.record_latency(time.time() - response_start)

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


# ═══════════════════════════════════════════════════════════
# CEO 项目执行
# ═══════════════════════════════════════════════════════════

@app.post("/v1/run")
async def run_project(request: Request) -> dict:
    """CEO 一键项目执行 — 提交需求描述，返回执行日志"""
    body = await request.json()
    request_text = body.get("request", "")
    if not request_text:
        return _error_response(400, "invalid_request", "request is required")

    tenant = getattr(request.state, "tenant", "anonymous")
    _log_request(tenant, "run_project", "", len(request_text))

    try:
        from dong_ai.ceo import CEO
        import io, sys
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        ceo = CEO()
        ceo.run(request_text)
        sys.stdout = old_stdout
        log = captured.getvalue()
    except Exception as e:
        _metrics.inc_error("ceo_error")
        return _error_response(500, "internal_error", f"CEO execution failed: {str(e)[:200]}")

    return {"status": "done", "log": log, "report_path": str(ceo.report_path)}


# ═══════════════════════════════════════════════════════════
# Webhook
# ═══════════════════════════════════════════════════════════

WEBHOOK_SECRET = os.environ.get("DONG_WEBHOOK_SECRET", os.environ.get("DONG_WEBHOOK_TOKEN", ""))


@app.post("/webhook")
async def webhook(request: Request) -> dict:
    """通用 webhook 接收器 — 接收 GitHub/GitLab 等事件"""
    body = await request.json()
    event = body.get("event", body.get("type", "unknown"))
    payload = body.get("payload", body)

    # 验证 secret
    token = request.headers.get("X-Webhook-Token", "")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        return _error_response(401, "webhook_invalid", "Invalid webhook token")

    # 记录
    try:
        from dong_ai.ceo_memory import CEOMemory
        mem = CEOMemory()
        sid = mem.session_start(f"webhook_{int(time.time())}")
        mem.session_save(sid, "system",
                         f"Webhook received: {event}\nPayload: {json.dumps(payload, ensure_ascii=False)[:1000]}")
    except Exception:
        pass

    _log_request("webhook", f"event:{event}", "", len(json.dumps(payload)))

    # 执行动作
    if event in ("deploy", "push"):
        try:
            from dong_ai.ceo import CEO
            import threading
            threading.Thread(target=CEO().run,
                             args=(f"审计最近的代码变更: {json.dumps(payload, ensure_ascii=False)[:200]}",),
                             daemon=True).start()
            return {"status": "accepted", "message": "Code audit started"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "received", "event": event}


# ═══════════════════════════════════════════════════════════
# Web UI
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def chat_ui():
    """Dong AI 聊天界面"""
    html_path = Path(__file__).parent / "chat_ui.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dong AI Company</h1><p>Chat UI not found</p>")


# ═══════════════════════════════════════════════════════════
# 优雅关闭
# ═══════════════════════════════════════════════════════════

@app.on_event("shutdown")
async def shutdown() -> None:
    """优雅关闭 — 清理资源"""
    from dong_ai.logger import get_logger
    get_logger("api").info("shutdown", reason="server_stopping")
    # 关闭 MCP 客户端连接等
    try:
        from dong_ai.mcp_client import _cleanup_all
        _cleanup_all()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════

def _log_request(tenant: str, endpoint: str, model: str, msg_count: int) -> None:
    """结构化请求日志（供内部调用）"""
    from dong_ai.logger import get_logger
    log = get_logger("api")
    log.info("request", tenant=tenant, endpoint=endpoint, model=model, messages=msg_count)


# ═══════════════════════════════════════════════════════════
# 启动验证
# ═══════════════════════════════════════════════════════════

def _validate_startup_config() -> None:
    """启动时配置验证"""
    import warnings
    api_key = os.environ.get("DONG_API_KEY", "")
    if api_key and len(api_key) < 16:
        warnings.warn("DONG_API_KEY is too short (< 16 chars). Use 'dong key create' to generate secure keys.")

    # 端口可用性（由 uvicorn 处理）
    # 日志目录
    Path.home().joinpath(".dong", "logs").mkdir(parents=True, exist_ok=True)

    # 速率限制配置验证
    rate = os.environ.get("DONG_RATE_LIMIT", "60")
    try:
        r = float(rate)
        if r <= 0:
            warnings.warn(f"DONG_RATE_LIMIT={rate} is invalid, using 60")
    except ValueError:
        warnings.warn(f"DONG_RATE_LIMIT={rate} is not a number, using 60")


# 启动时执行
_validate_startup_config()
