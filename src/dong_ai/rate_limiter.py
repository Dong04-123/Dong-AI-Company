"""
Dong AI — Token Bucket Rate Limiter

按 API Key + 端点的速率限制。内存中，无外部依赖。

配置（环境变量）:
  DONG_RATE_LIMIT=60          # 每分钟允许的请求数（默认 60）
  DONG_RATE_BURST=10          # 突发允许的额外请求数（默认 10）

用法:
  from .rate_limiter import RateLimiter
  limiter = RateLimiter()
  allowed, retry_after = limiter.check("key-xxx", "/v1/chat/completions")
  if not allowed:
      return 429 + Retry-After header
"""

from __future__ import annotations

import os, time, threading
from typing import Optional


class TokenBucket:
    """单个令牌桶"""

    def __init__(self, rate: float, burst: int) -> None:
        self.rate = rate               # 令牌/秒
        self.burst = burst             # 最大令牌数
        self.tokens = float(burst)     # 当前令牌
        self._last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> tuple[bool, float]:
        """消费 tokens 个令牌。返回 (是否允许, 等待多少秒后重试)"""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self._last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0

            wait = (tokens - self.tokens) / self.rate
            return False, wait


class RateLimiter:
    """多 Key + 端点的速率限制器"""

    def __init__(self) -> None:
        self._rate = float(os.environ.get("DONG_RATE_LIMIT", "60"))
        self._burst = int(os.environ.get("DONG_RATE_BURST", "10"))
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._auto_adjust = os.environ.get("DONG_RATE_AUTO_ADJUST", "1") == "1"

    def _bucket_key(self, tenant: str, endpoint: str) -> str:
        return f"{tenant}:{endpoint}"

    def check(self, tenant: str, endpoint: str) -> tuple[bool, float]:
        """检查请求是否允许。返回 (allowed, retry_after_seconds)"""
        key = self._bucket_key(tenant, endpoint)
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = TokenBucket(self._rate, self._burst)
            bucket = self._buckets[key]

        allowed, wait = bucket.consume()
        return allowed, wait

    def get_remaining(self, tenant: str, endpoint: str) -> int:
        """获取剩余令牌数"""
        key = self._bucket_key(tenant, endpoint)
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                return self._burst
            # refill first
            now = time.monotonic()
            elapsed = now - bucket._last_refill
            tokens = min(bucket.burst, bucket.tokens + elapsed * bucket.rate)
            return max(0, int(tokens))

    def get_reset_time(self, tenant: str, endpoint: str) -> float:
        """获取速率重置时间（秒）"""
        key = self._bucket_key(tenant, endpoint)
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                return 0.0
            return max(0.0, (bucket.burst - bucket.tokens) / bucket.rate) if bucket.tokens < bucket.burst else 0.0

    def stats(self) -> dict:
        """速率限制统计"""
        with self._lock:
            return {
                "rate_per_second": self._rate,
                "burst": self._burst,
                "active_buckets": len(self._buckets),
                "auto_adjust": self._auto_adjust,
            }
