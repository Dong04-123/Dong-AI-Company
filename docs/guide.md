# Dong AI Company — 用户指南

## 安装

```bash
pip install dong-ai
# 或包含全部依赖
pip install 'dong-ai[all]'
```

## 快速上手

### 1. 配置向导

```bash
dong setup
```

自动检测硬件 → 选择运行模式 → 选择模型 → 配置上下文 → 保存。

### 2. 日常使用

```bash
dong chat           # 交互式对话
dong run "需求"     # 一键项目执行
```

### 3. 启动 API 服务

```bash
pip install 'dong-ai[server]'
dong serve          # 默认 http://localhost:8648
```

浏览器打开即用，或任何 OpenAI 兼容客户端连接。

## 命令参考

| 命令 | 说明 |
|------|------|
| `dong chat` | 交互式 TUI |
| `dong run "需求"` | 一键项目执行，CEO + WorkerPool 全流程 |
| `dong serve` | 启动 OpenAI 兼容 API 服务 |
| `dong setup` | 交互式配置向导 |
| `dong detect` | 检测可用模型和硬件 |
| `dong version` | 版本信息 |
| `dong config list` | 查看全部配置 |
| `dong config set key=val` | 修改配置 |
| `dong config get key` | 查看单项配置 |
| `dong skill list` | 列出所有可用技能 |
| `dong skill create name=desc` | 创建新技能 |
| `dong session list` | 查看最近会话 |
| `dong session view <id>` | 查看会话详情 |
| `dong mcp` | 发现 MCP 服务器和工具 |
| `dong cron list` | 列出定时任务 |
| `dong cron add --cmd "..." --every 30m` | 添加定时任务 |
| `dong cron start` | 启动定时调度器 |
| `dong cron remove <id>` | 删除定时任务 |
| `dong webhook list` | 列出 webhook 配置 |
| `dong webhook set-url <url>` | 配置 webhook 地址 |

## TUI 命令

在 `dong chat` 中可用的内部命令：

| 命令 | 说明 |
|------|------|
| `/dash` | 仪表盘 — 显示模型/Token/图记忆 |
| `/soul` | 查看 CEO 人格 |
| `/soul set <text>` | 设置 CEO 人格 |
| `/mode` | 切换模式 (MINI/PRO) |
| `/resume` | 恢复上次会话 |
| `/search <q>` | 搜索记忆 |
| `/export` | 导出数据 |
| `/config set key=val` | 实时修改配置 |
| `/help` | 帮助 |
| `/exit` | 退出 |

## 配置说明

### 运行模式

```bash
dong config set mode=api      # 云端：256K上下文，API模型优先
dong config set mode=local    # 本地：64K上下文，本地模型优先
dong config set mode=auto     # 自动检测（推荐）
```

### 上下文窗口

```bash
dong config set ceo_context=256000    # CEO 上下文窗口 (默认 API:256K / Local:64K)
dong config set ceo_max_tokens=16384  # CEO 最大回复长度
dong config set worker_context=128000 # 工人上下文窗口
dong config set worker_max_tokens=8192 # 工人最大回复长度
```

### 其他配置

```bash
dong config set temperature=0.7       # 模型温度
dong config set auto_compress_at=30   # 多少条消息后自动压缩
dong config set keep_recent=20        # 压缩时保留最近多少条
```

## API 服务

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/models` | GET | 可用模型列表 (OpenAI 兼容) |
| `/v1/chat/completions` | POST | 聊天补全 (OpenAI 兼容，支持流式) |
| `/v1/run` | POST | CEO 一键项目执行 |
| `/webhook` | POST | 接收外部事件 |
| `/health` | GET | 健康检查 |
| `/` | GET | Web 聊天界面 |

### 示例

```bash
curl http://localhost:8648/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

## 双模式对比

| 特性 | API 模式 | 本地模式 |
|------|---------|---------|
| CEO 上下文 | 256K | 64K |
| 工人上下文 | 128K | 64K |
| 模型选择 | DeepSeek/OpenAI 优先 | 本地模型优先 |
| 适用场景 | 有 API Key、需要大窗口 | 本地 GPU、隐私优先 |
| 自动压缩 | 30 条触发 | 12 条触发 |

## 定时任务

```bash
# 每小时执行一次审计
dong cron add --cmd "dong run '系统审计'" --every 1h --name "每小时审计"

# 查看任务
dong cron list

# 启动调度器（后台运行）
dong cron start
```

## Webhook

```bash
# 配置接收地址
dong webhook set-url https://your-server.com/webhook

# 设置认证密钥
export DONG_WEBHOOK_SECRET=your-secret

# 发送事件（支持 push/deploy 等）
curl -X POST http://localhost:8648/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Token: your-secret" \
  -d '{"event": "deploy", "payload": {"branch": "main"}}'
```

## MCP 集成

MCP (Model Context Protocol) 让 AI 公司可以调用外部工具。

```bash
# 发现已配置的 MCP 服务器
dong mcp

# 配置 MCP 服务器 (创建 .mcp.json)
# {"mcpServers": {"filesystem": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]}}}
```

## 技能系统

```bash
# 列出所有技能（包含 Hermes 125+ 技能）
dong skill list

# 创建新技能
dong skill create name=my-skill description=我的自定义技能
```

技能文件存储在 `~/.dongcode/skills/`，自动扫描 `~/.hermes/skills/`。

## 常见问题

### 为什么启动后显示 "没有可用模型"？
运行 `dong detect` 查看当前配置的 API key 和本地模型状态。至少需要配置一个 API key 或启动本地模型。

### 如何切换到另一个模型？
```bash
dong config set mode=api     # 使用 API 模型
dong config set mode=local   # 使用本地模型
# 或手动设置 provider
```

### 图记忆数据存在哪里？
`~/.dong/dong.db` 的 `codegraph` 和 `code_deps` 表。

### 如何完全重置？
```bash
rm -rf ~/.dong
```
