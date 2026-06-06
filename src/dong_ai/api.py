"""Dong AI — FastAPI API Server

OpenAI 兼容 API，任何 OpenAI 客户端可直接连接。

启动:
  dong serve --port 8648

端点:
  GET  /v1/models              → 可用模型列表
  POST /v1/chat/completions    → 聊天（含流式）
  POST /v1/run                 → CEO 项目执行
  GET  /health                 → 健康检查
"""

import json, time, uuid, os
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pathlib import Path
except ImportError:
    raise ImportError("需要安装 fastapi: pip install 'dong-ai[server]'")

from dong_ai.model_pool import ModelPool

app = FastAPI(title="Dong AI API", version="0.1.0")
pool = ModelPool()


# ═══════════════════════════════════════════════════════════
# Models (OpenAI 兼容)
# ═══════════════════════════════════════════════════════════

@app.get("/v1/models")
async def list_models():
    """OpenAI 兼容的模型列表"""
    providers = pool.available()
    models = []
    for p in providers:
        for model_id in p["models"]:
            models.append({
                "id": model_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": p["name"],
            })
    return {"object": "list", "data": models}


# ═══════════════════════════════════════════════════════════
# Chat Completions (OpenAI 兼容)
# ═══════════════════════════════════════════════════════════

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容的聊天补全（支持流式）"""
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "")
    stream = body.get("stream", False)
    max_tokens = body.get("max_tokens", 8192)
    temperature = body.get("temperature", 0.7)

    # 从 messages 中提取 system prompt
    system = ""
    filtered = []
    for m in messages:
        if m.get("role") == "system":
            system = m["content"]
        else:
            filtered.append(m)
    messages = filtered

    # 选择 provider（如果指定 model 则匹配，否则用 best）
    providers = pool.available()
    if model:
        target = next((p for p in providers if model in p["models"]), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Model {model} not found")
        providers = [target]

    if not providers:
        raise HTTPException(status_code=503, detail="No available model providers")

    if stream:
        return _stream_response(providers[0], messages, system, max_tokens, temperature, model)
    else:
        return _json_response(providers[0], messages, system, max_tokens, temperature, model)


def _json_response(provider, messages, system, max_tokens, temperature, model_id):
    """非流式响应"""
    from dong_ai.llm import LLMConfig, OpenAICompatibleClient

    client = OpenAICompatibleClient(LLMConfig(
        model=model_id or provider["models"][0],
        base_url=provider["base_url"],
        api_key=provider.get("api_key", ""),
        max_tokens=max_tokens,
        temperature=temperature,
    ))

    try:
        resp = client.chat(messages, system=system if system else None)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_id or provider["models"][0],
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": resp.text},
            "finish_reason": "stop",
        }],
        "usage": resp.usage,
    }


def _stream_response(provider, messages, system, max_tokens, temperature, model_id):
    """流式 SSE 响应"""
    from dong_ai.llm import LLMConfig, OpenAICompatibleClient

    client = OpenAICompatibleClient(LLMConfig(
        model=model_id or provider["models"][0],
        base_url=provider["base_url"],
        api_key=provider.get("api_key", ""),
        max_tokens=max_tokens,
        temperature=temperature,
    ))

    async def generate():
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model_id or provider['models'][0], 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"

        try:
            for token in client.chat_stream(messages, system=system if system else "", max_tokens=max_tokens, temperature=temperature):
                yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model_id or provider['models'][0], 'choices': [{'index': 0, 'delta': {'content': token}, 'finish_reason': None}]})}\n\n"

            yield f"data: {json.dumps({'id': completion_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': model_id or provider['models'][0], 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': {'message': str(e)}})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


# ═══════════════════════════════════════════════════════════
# CEO 项目执行
# ═══════════════════════════════════════════════════════════

@app.post("/v1/run")
async def run_project(request: Request):
    """CEO 一键项目执行"""
    body = await request.json()
    request_text = body.get("request", "")
    if not request_text:
        raise HTTPException(status_code=400, detail="request is required")

    try:
        from dong_ai.ceo import CEO
        import io, sys
        # 捕获 print 输出作为执行日志
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        ceo = CEO()
        ceo.run(request_text)
        sys.stdout = old_stdout
        log = captured.getvalue()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "done", "log": log, "report_path": str(ceo.report_path)}


# ═══════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    providers = pool.available()
    return {
        "status": "ok",
        "version": "0.1.0",
        "providers": len(providers),
        "models": [p["models"][0] for p in providers[:5]],
    }


# ═══════════════════════════════════════════════════════════
# Webhook
# ═══════════════════════════════════════════════════════════

WEBHOOK_SECRET = os.environ.get("DONG_WEBHOOK_SECRET", "")


@app.post("/webhook")
async def webhook(request: Request):
    """通用 webhook 接收器——接收外部事件并触发动作"""
    body = await request.json()
    event = body.get("event", body.get("type", "unknown"))
    payload = body.get("payload", body)

    # 验证 secret
    token = request.headers.get("X-Webhook-Token", "")
    if WEBHOOK_SECRET and token != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="invalid token")

    # 记录 webhook
    try:
        from dong_ai.ceo_memory import CEOMemory
        mem = CEOMemory()
        sid = mem.session_start(f"webhook_{int(time.time())}")
        mem.session_save(sid, "system",
                         f"Webhook received: {event}\nPayload: {json.dumps(payload, ensure_ascii=False)[:1000]}")
    except Exception:
        pass

    # 根据事件类型执行动作
    if event == "deploy" or event == "push":
        # 触发 CEO 审计
        try:
            from dong_ai.ceo import CEO
            ceo = CEO()
            # 后台线程执行
            import threading
            threading.Thread(target=ceo.run,
                             args=(f"审计最近的代码变更: {json.dumps(payload, ensure_ascii=False)[:200]}",),
                             daemon=True).start()
            return {"status": "accepted", "message": "审计已启动"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "received", "event": event}


# ═══════════════════════════════════════════════════════════
# Web UI
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def chat_ui():
    """Kimi 风格的聊天界面"""
    html_path = Path(__file__).parent / "chat_ui.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dong AI Company</h1><p>Chat UI not found</p>")
