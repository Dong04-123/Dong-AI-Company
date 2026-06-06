<div align="center">

```
██████╗  ██████╗ ███╗   ██╗ ██████╗     █████╗ ██╗
██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗██║
██║  ██║██║   ██║██╔██╗ ██║██║         ███████║██║
██║  ██║██║   ██║██║╚██╗██║██║         ██╔══██║██║
██████╔╝╚██████╔╝██║ ╚████║╚██████╗    ██║  ██║██║
╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝  ╚═╝╚═╝

# Dong AI Company

**Your Private AI Company**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Dong04-123/Dong-AI-Company/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-121%20passed-brightgreen)](tests/)
[![Providers](https://img.shields.io/badge/providers-20%2B-orange)](src/dong_ai/model_pool.py)
[![PyPI](https://img.shields.io/pypi/v/dong-ai)](https://pypi.org/project/dong-ai/)

`pip install dong-ai`

</div>

---

Dong AI is not another agent framework. It's an **AI company with full organizational governance** — red/blue team debate for decision making, dynamic worker pools for execution, graph memory for contextual coherence across large projects, and board review for quality gates. Works for software development, novel writing, game development, data analysis, code audit, and any project type.

---

## Core Capabilities

### 🏛️ AI Company Governance

Unlike traditional AI agents that operate as stateless chat interfaces, Dong AI implements a **full corporate decision-making pipeline**: each project undergoes structured debate, execution is distributed across dynamically assembled specialist workers, and every phase exits through a quality gate enforced by board-level scoring.

```
User Request → CEO → Red/Blue Debate → Design + Requirements
    → Worker Pool (cross-review + automated tests)
    → Board Review → Phase Gate (≥ 6.0/10)
    → Next Phase or Terminate
```

### 🧠 Graph Memory

Conventional LLM applications lose context beyond their window limit. Dong AI's **graph memory layer** persists structured knowledge across sessions:

- **Symbol indexing**: Every function, class, interface, and dependency is automatically extracted and stored in a queryable graph database
- **Contextual injection**: When starting a new task, the system queries the graph for relevant symbols, signatures, and dependency relationships — delivering precise context instead of raw text
- **Cross-phase coherence**: Phase 3 can reference symbols defined in Phase 1 with exact signatures, not vague descriptions
- **Requirement traceability**: Each task's output is linked back to specific design requirements, enabling coverage analysis and quality scoring

This architecture supports **coherent development across large, multi-phase projects** — not by stuffing text into a context window, but by maintaining a structured, queryable knowledge graph.

### 🔌 Ecosystem Integration

| Integration | Method |
|-------------|--------|
| **Hermes Skills** (125+) | Direct scan of `~/.hermes/skills/` |
| **MCP Protocol** | Discover and invoke any MCP server tool |
| **OpenAI API** | `dong serve` — any OpenAI client connects |
| **20+ Providers** | DeepSeek / OpenAI / Claude / Groq / Together / Local / Ollama |
| **Local Models** | Qwen / Llama / any GGUF — auto failover |
| **Webhook** | `POST /webhook` for external event triggers |
| **Scheduled Tasks** | `dong cron add --cmd "dong run audit" --every 1h` |

### ⚙️ Dual-Mode Architecture

| Mode | CEO Context | Worker Context | Best For |
|------|-------------|----------------|----------|
| **API** | 256K | 128K | Cloud models (DeepSeek/GPT/Claude) |
| **Local** | 64K | 64K | Local deployment (Qwen/Llama/Ollama) |
| **Custom** | Any | Any | `dong config set ceo_context=999999` |

### 📋 Dynamic Project Pipeline

The CEO automatically identifies project type and generates a custom execution pipeline via LLM. No hardcoded workflows — every project gets a tailored plan.

| Input | Detection | Generated Pipeline |
|-------|-----------|-------------------|
| "Build a config system" | software | Scaffold → Core → Test → Release |
| "Write a cyberpunk novel" | novel | World-building → Characters → Chapters → Revision |
| "Develop a pixel RPG" | game | Design doc → Mechanics → Content → Build |
| "Analyze this architecture" | analysis | Collection → Analysis → Report |
| "Audit this codebase" | audit | Scope → Review → Findings |

Each phase is executed by **dynamically recruited workers** (generated by LLM based on task requirements), then undergoes **cross-review**, **automated testing**, and **board scoring** with a minimum quality gate of 6.0/10.

---

## Demo

```bash
$ dong run "Build a configuration manager"

█══════════════════════════════════════════════════════█
  Dong AI 启动 | Build a configuration manager
█══════════════════════════════════════════════════════█

  📋 识别项目类型: 💻 软件开发
  📚 加载 3 个相关技能

  📋 设计阶段
  ┊  ◆ 红队: 方案A — YAML+JSON双格式支持
  ┊  ◆ 蓝队: 方案B — 仅JSON
  ┊  ★ 董事会: 评分 8.5，采纳方案A
  ✅ 设计完成

  📋 执行 1/4: 架构搭建 → ✅ 5文件 3/3测试
  📋 执行 2/4: 核心开发 → ✅ 5文件 9/9测试
  📋 执行 3/4: 测试集成 → ✅ 全部通过
  📋 执行 4/4: 文档发布 → ✅ README+CHANGELOG

  📋 评分: 8.2 | 需求覆盖率: 6/6
  ✅ 项目完成 | 报告: final_report.md
```

---

## Quick Start

```bash
# Installation
pip install dong-ai
pip install 'dong-ai[all]'     # full dependencies incl. API server

# Interactive setup wizard — detects hardware, selects mode, configures context
dong setup

# Start interactive TUI
dong chat

# One-click project execution
dong run "Build a configuration management system"

# Start OpenAI-compatible API server → http://localhost:8648
dong serve
```

### Command Reference

```
dong chat          Interactive TUI          dong config      Manage configuration
dong run "req"     One-click execution       dong skill       List/create skills
dong serve         API server                dong session     View chat history
dong setup         Setup wizard              dong mcp         Discover MCP tools
dong detect        Detect available models   dong cron        Scheduled tasks
dong version       Version info              dong webhook     Webhook management
```

---

## Architecture

```
User Layer:       dong chat / dong run / dong serve / API clients

Orchestration:    CEO → DesignEngine(Red/Blue debate) → WorkerPool(self-heal, cross-review)

Engine Layer:     ModelPool(20+ providers, auto failover) → LLMClient(unified HTTP/SSE)

Storage Layer:    Datastore(SQLite)
                  ├── MemoryRepository      Fact KV
                  ├── SessionRepository     Conversation history
                  ├── ProjectRepository     Decisions & module states
                  ├── LoreRepository        World-building (novel mode)
                  └── GraphRepository       Code symbols, dependencies, requirements trace
```

---

## Testing

```bash
pip install pytest
pytest tests/
# 121 tests, all passing in ~1.6s
# Zero external dependencies — no network calls, no API keys required
```

---

## License

MIT — free for personal, research, and commercial use. Attribution required.

---

<div align="center">
  <sub>Not a chatbot — your AI workforce.</sub>
</div>
