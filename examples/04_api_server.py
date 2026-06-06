#!/usr/bin/env python3
"""
Example 4: API server — test auth, rate limiting, health check.

Shows how to start the Dong AI API and interact with it.
Requires: pip install 'dong-ai[server]'

Run:
  python3 examples/04_api_server.py
"""

import json, urllib.request


def main():
    print("╭─ Dong AI — API Server Demo ─────────────────────╮")
    print("┊")
    print("┊  Start the server in another terminal:")
    print("┊    DONG_API_KEY=sk-demo-key dong serve --port 8648")
    print("┊")
    print("┊  Then run this example to see:")
    print("┊")

    base = "http://localhost:8648"
    key = "sk-demo-key"

    def req(method, path, data=None):
        url = f"{base}{path}"
        headers = {"Authorization": f"Bearer {key}"}
        if data:
            headers["Content-Type"] = "application/json"
            data = json.dumps(data).encode()
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            return json.loads(urllib.request.urlopen(r).read())
        except urllib.error.HTTPError as e:
            return {"error": e.code, "body": e.read().decode()[:200]}

    # Test health
    print("┊  1. GET /health →", end=" ")
    result = req("GET", "/health")
    if result.get("status") == "ok":
        print(f"OK (uptime: {result.get('uptime_seconds', '?')}s)")
    else:
        print(f"Server not running (expected if server is down)")
        print("┊     Start server first with the command above")
        print("╰──────────────────────────────────────────────────╯")
        return

    # Test models
    print("┊  2. GET /v1/models →", end=" ")
    result = req("GET", "/v1/models")
    models = result.get("data", [])
    print(f"{len(models)} models available")

    # Test rate limit headers
    print("┊  3. Rate limit headers →", end=" ")
    resp = urllib.request.urlopen(urllib.request.Request(
        f"{base}/v1/models",
        headers={"Authorization": f"Bearer {key}"}
    ))
    print(f"Limit: {resp.headers.get('X-RateLimit-Limit', '?')}, "
          f"Remaining: {resp.headers.get('X-RateLimit-Remaining', '?')}")

    # Test metrics
    print("┊  4. GET /metrics →", end=" ")
    result = req("GET", "/metrics")
    if isinstance(result, str) and "dong_requests_total" in result:
        print("Prometheus OK")
    elif isinstance(result, dict) and "error" not in result:
        print("OK")
    else:
        print("OK (plaintext)")

    print("┊")
    print("╰──────────────────────────────────────────────────╯")


if __name__ == "__main__":
    main()
