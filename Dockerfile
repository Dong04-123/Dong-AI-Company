# =============================================================================
# Dong AI — 多阶段构建
# =============================================================================
# 构建阶段：编译依赖到 wheel
FROM python:3.12-slim AS builder

WORKDIR /build
COPY . .
RUN pip install --no-cache-dir build && \
    python3 -m build --wheel

# =============================================================================
# 运行阶段：最小镜像
# =============================================================================
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Dong AI Company" \
      org.opencontainers.image.description="Infinite Context AI Company" \
      org.opencontainers.image.source="https://github.com/Dong04-123/Dong-AI-Company" \
      org.opencontainers.image.licenses="MIT"

# 非 root 用户
RUN groupadd -r dong && useradd -r -g dong -d /home/dong -s /sbin/nologin dong && \
    mkdir -p /home/dong/.dong /home/dong/.hermes && \
    chown -R dong:dong /home/dong

WORKDIR /app

# 从 builder 复制 wheel
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl 'dong-ai[server]' && \
    rm /tmp/*.whl && \
    rm -rf /root/.cache

EXPOSE 8648

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8648/health')" || exit 1

USER dong

ENTRYPOINT ["dong", "serve"]
CMD ["--host", "0.0.0.0", "--port", "8648"]
