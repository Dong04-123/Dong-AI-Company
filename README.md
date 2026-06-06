# Dong AI Company

**您的私人AI公司。** 一个命令拉起一家 AI 企业——红蓝辩论决策、动态工人池执行、董事会评分质量门。

```bash
pip install dong-ai
dong setup        # 交互式配置
dong run "开发配置系统"  # 一键项目执行
dong serve        # OpenAI 兼容 API
```

---

## 为什么是 AI 公司？

现有 AI Agent 是"工具"——你问它答，最多帮你写代码。

Dong AI 是**一家公司**：

```
你: "开发一个配置系统"

CEO: 收到需求 → 组建项目组
  ├─ 红队: 提出方案 A（安全但慢）
  ├─ 蓝队: 提出方案 B（快但有风险）
  ├─ 董事会: 评分 8.5，采纳方案 A
  │
  ├─ 工人池: 3 名员工并行执行
  │   ├─ 代码匠 → 写 config_loader.py  ✓
  │   ├─ 测试判官 → 写 test_config.py  ✓
  │   └─ 架构师 → 交叉审查 ✓
  │
  ├─ 自愈重试: 测试失败 → 自动修复 → 重跑 ✓
  ├─ 董事会: 最终评分 8.2 → 报告 ✓
  └─ 图记忆: 所有接口/符号/依赖已记录
```

不是聊天工具——是你的 AI 员工团队。

---

## 特性

### 🏛️ 公司治理流水线

```
设计(红蓝辩论) → 计划(依赖拆解) → 执行(工人池+自愈+互审) → 董事会评分 → 需求锁
```

每阶段出口检查需求覆盖率，评分低于阈值不放行。

### 🧠 图记忆系统

不是全量塞上下文——是**需要什么查什么**：

```
load_config(path: str) → dict        # 精确签名
YAMLConfig → Config [inherits]       # 继承关系
validate_schema → load_config [calls] # 调用图
```

新任务自动注入相关符号和依赖，工人永远知道上下文。

### 🔌 开放生态

| 集成 | 方式 |
|------|------|
| **Hermes Skills** | 直接扫描 `~/.hermes/skills/`，125+技能立即可用 |
| **MCP 协议** | 发现并调用任何 MCP 服务器工具 |
| **OpenAI API** | `dong serve` → 任何 OpenAI 客户端直接连接 |
| **20+ Provider** | DeepSeek / OpenAI / Claude / Groq / Together / 本地模型 / Ollama |
| **本地模型** | Qwen / Llama / 任何 GGUF — 自动 failover |
| **Webhook** | `POST /webhook` 接收外部事件触发审计 |

### ⚙️ 双模式设计

```
API 模式（云端）         Local 模式（本地）
──────────────────────────────────────
CEO 64K 上下文          CEO 64K 上下文
工人 32K 上下文          工人 64K 上下文
自动压缩宽松             自动压缩宽松
DeepSeek/GPT 优先        本地模型优先
```

用户可自由设置，`dong config set ceo_context=999999` 永不限制。

---

## 快速开始

```bash
# 安装
pip install dong-ai

# 交互式配置向导
dong setup

# 启动 TUI
dong chat

# 一键项目执行
dong run "帮我开发一个文件监控系统"

# 启动 API 服务（OpenAI 兼容）
pip install 'dong-ai[server]'
dong serve
# → 浏览器 http://localhost:8648
# → 任何 OpenAI 客户端可用
```

### 详细命令

```
dong chat                  交互式 TUI
dong run "需求"            一键项目执行
dong serve                 启动 API 服务
dong setup                 交互式配置向导
dong detect                检测可用模型
dong config [list|set|get] 配置管理
dong skill [list|create]   技能管理
dong session [list|view]   会话管理
dong mcp                   发现 MCP 工具
dong cron [list|add|start] 定时任务
dong webhook [list|set]    Webhook 管理
dong version               版本信息
```

---

## 架构

```
dong chat / dong run / dong serve
        │
   ┌────┴────┐
   │  CEO    │ ← DesignEngine(红蓝辩论) + WorkerPool(工人+自愈+互审)
   └────┬────┘
        │
   ┌────┴────┐
   │ ModelPool│ ← 20+ Provider 自动 failover
   └────┬────┘
        │
   ┌────┴────┐
   │ LLMClient│ ← 统一 HTTP + SSE
   └─────────┘

存储层:
  Datastore (SQLite)
  ├── MemoryRepository  →  Fact KV
  ├── SessionRepository →  会话历史
  ├── ProjectRepository →  决策/模块
  ├── LoreRepository    →  世界观
  └── GraphRepository   →  代码符号/依赖/需求追溯
```

---

## 测试

```bash
pip install pytest
pytest tests/
# 121 passed in 1.6s
```

---

## 许可证

MIT
