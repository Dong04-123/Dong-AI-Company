FROM python:3.12-slim

WORKDIR /app

# 安装 dong-ai
COPY . /app/
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir 'dong-ai[server]'

# 暴露 API 端口
EXPOSE 8648

# 启动服务
ENTRYPOINT ["dong", "serve"]
CMD ["--host", "0.0.0.0", "--port", "8648"]
