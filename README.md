# Dong AI Company

<div align="center">

**您的私人AI公司 — 一个命令拉起一家AI企业**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Dong04-123/Dong-AI-Company/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-121%20passed-brightgreen)](tests/)
[![Providers](https://img.shields.io/badge/providers-20%2B-orange)](src/dong_ai/model_pool.py)
[![Context](https://img.shields.io/badge/context-256K%2B-purple)](#)

</div>

```bash
pip install dong-ai
dong setup
```

---

## 为什么是 AI 公司？

现有 AI Agent 是"工具"——你问它答，最多帮你写代码。  
Dong AI 是**一家公司**——有红蓝辩论决策、有工人池执行、有董事会评分质量门。

```
你: "开发配置系统"          工人池              董事会
  │                          │                  │
  ├─ 红队: 方案A(安全但慢)    ├─ 代码匠 → 写文件  ├─ 评分8.5
  ├─ 蓝队: 方案B(快有风险)    ├─ 测试判官 → 测试  ├─ 覆盖检查
  └─ CEO: 采纳方案A          └─ 审查 → 通过      └─ 放行下一阶段
```

## 特性

| 能力 | 说明 |
|------|------|
| 🏛️ **治理流水线** | 红蓝辩论 → 依赖拆解 → 工人池(自愈+互审) → 董事会评分 → 需求锁 |
| 🧠 **图记忆** | 精确符号索引 + 依赖关系，新任务自动注入相关上下文 |
| 🔌 **开放生态** | Hermes 125+ 技能 / MCP 协议 / OpenAI API 兼容 |
| 🌐 **20+ Provider** | DeepSeek / OpenAI / Claude / Groq / Together / 本地 / Ollama |
| ⚙️ **双模式** | API 模式(256K 窗口) / 本地模式(64K 窗口) / 用户自由设置 |
| 🕐 **定时任务** | `dong cron add --cmd "dong run 审计" --every 1h` |
| 📡 **Webhook** | `POST /webhook` 触发自动审计 |
| 🔗 **MCP 客户端** | 发现并调用任何 MCP 服务器工具 |

## 快速开始

```bash
pip install dong-ai
pip install 'dong-ai[all]'    # 全部依赖（含 API 服务）

dong setup                     # 交互式配置向导
dong chat                      # 启动对话
dong run "配置系统"            # 一键项目执行
dong serve                     # 启动 API 服务 → http://localhost:8648
```

### 命令一览

```
dong chat          交互式 TUI         dong config     配置管理
dong run "需求"    一键项目执行        dong skill      技能管理
dong serve         API 服务           dong session    会话管理
dong setup         配置向导           dong mcp        MCP 工具发现
dong detect        模型检测           dong cron       定时任务
dong version       版本信息           dong webhook    Webhook 管理
```

## 架构

```
dong chat / dong run / dong serve
        │
   ┌────┴────┐
   │  CEO    │  ← DesignEngine(红蓝辩论) + WorkerPool(自愈+互审)
   └────┬────┘
        │
   ┌────┴────┐
   │ ModelPool│  ← 20+ Provider 自动 failover
   └────┬────┘
        │
   ┌────┴────┐
   │ LLMClient│  ← 统一 HTTP + SSE
   └─────────┘

存储层:
  Datastore (SQLite)
  ├── MemoryRepository     事实 KV
  ├── SessionRepository    会话历史
  ├── ProjectRepository    决策/模块
  ├── LoreRepository       世界观
  └── GraphRepository      代码符号/依赖/需求追溯
```

## 双模式配置

```
模式        CEO 上下文    工人上下文    适用场景
─────────────────────────────────────────────────
API        256K          128K         云端模型(DeepSeek/GPT/Claude)
Local      64K           64K          本地模型(Qwen/Llama/Ollama)
自定义     任意           任意         dong config set ceo_context=999999
```

## 测试

```bash
pip install pytest
pytest tests/
# 121 passed in 1.6s
```

## 许可证

MIT — 随意使用、修改、商用。

---

<p align="center">
  <sub>不是聊天工具——是你的 AI 员工团队</sub>
</p>
