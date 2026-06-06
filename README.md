<div align="center">

```
██████╗  ██████╗ ███╗   ██╗ ██████╗     █████╗ ██╗
██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗██║
██║  ██║██║   ██║██╔██╗ ██║██║         ███████║██║
██║  ██║██║   ██║██║╚██╗██║██║         ██╔══██║██║
██████╔╝╚██████╔╝██║ ╚████║╚██████╗    ██║  ██║██║
╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝  ╚═╝╚═╝

# Dong AI Company — 把 AI 公司装进命令行

**🚀 Column Memory: 大项目永不丢失上下文 | 🧠 Experience Engine: 越做越会做 | 🏢 红蓝辩论+董事会+多工人 | 🔌 20种模型 | ⚡ 281测试 | 📦 pip install**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Dong04-123/Dong-AI-Company/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-281%20passed-brightgreen)](tests/)
[![Providers](https://img.shields.io/badge/providers-20%2B-orange)](src/dong_ai/model_pool.py)
[![PyPI](https://img.shields.io/pypi/v/dong-ai)](https://pypi.org/project/dong-ai/)
[![PyPI Downloads](https://img.shields.io/pypi/dm/dong-ai)](https://pypi.org/project/dong-ai/)

```bash
pip install dong-ai[all]
dong setup
dong run "帮我写一个CLI工具"
```

</div>

---

Dong AI is not another agent framework. It's an **AI company with infinite context** — graph memory eliminates window limits, enabling coherent development across ultra-large projects. Red/blue team debate for decision making, dynamic worker pools for execution, and board review for quality gates. Works for software development, novel writing, game development, data analysis, code audit, and any project type.

---

## 🚀 30秒体验 (不需要 API Key)

```bash
pip install dong-ai
dong check           # 系统检测，无 key 也会友好提示
dong setup           # 配置 API Key（支持20种模型）
dong run "写个CLI"   # 一键启动 AI 公司
dong detect          # 查看完整系统状态
```

---

## Core Capabilities

### 🏛️ AI Company Governance — Corporate-Grade Project Management

Traditional AI agents operate as stateless chat interfaces: ask a question, get an answer, forget everything. Dong AI implements a **full organizational governance structure** that mirrors how real engineering companies deliver projects.

```
User Request
    ↓
  CEO — Type detection → Pipeline generation → Worker recruitment
    ↓
  DesignEngine — Red/Blue team debate → Requirements extraction → Coverage checklist
    ↓
  WorkerPool — Dynamic role generation → Parallel execution → Self-healing (×3 retries) → Cross-review
    ↓
  BoardReview — Phase scoring (1-10) → Requirement coverage audit → Quality gate (≥ 6.0)
    ↓
  GraphMemory — Auto-index all symbols, dependencies, decisions → Persistent across sessions
    ↓
  Report — Full project report with evidence trail
```

**Key differentiators:**

- **Red/Blue team debate**: Two AI teams independently analyze design approaches, then debate trade-offs. The CEO selects the winner based on technical merit, not speed. This eliminates single-point-of-failure design decisions.
- **Dynamic worker recruitment**: No hardcoded roles. Each task generates its own specialist team via LLM — software projects get architects and engineers, novels get world-builders and writers, audits get security analysts. 160+ role pool.
- **Board review with phase gates**: Every phase is scored 1-10. Requirement coverage is audited against the design checklist. Below 6.0? The project terminates. No "ship now, fix later."
- **Self-healing execution**: Workers retry up to 3 times with full failure context. Cross-review catches integration issues before they propagate.

### 🧠 Infinite Context — Graph Memory Architecture

**The problem with every other AI system:** Context windows are finite. Close the conversation, lose the context. Even with 400K windows, the model must search through noise to find signal.

**Dong AI's solution:** A structured knowledge graph that persists across sessions, projects, and restarts. Not "remembering" — indexing.

```
┌────────────────────────────────────────────────────────────┐
│                    Graph Memory Layer                       │
├────────────────────────────────────────────────────────────┤
│  codegraph table              code_deps table              │
│  ┌──────────────────────┐    ┌────────────────────────┐   │
│  │ load_config          │    │ validate_schema        │   │
│  │   type: function     │    │   → load_config [calls]│   │
│  │   file: loader.py:5  │    │ watch_directory        │   │
│  │   sig: (path:str)   │    │   → load_config [calls]│   │
│  │   embedding: [...]   │    │ YAMLConfig             │   │
│  └──────────────────────┘    │   → Config [inherits]  │   │
│                              └────────────────────────┘   │
│                                                             │
│  Three retrieval methods:                                    │
│  ① Keyword match — exact signature lookup                   │
│  ② Semantic search — embedding cosine similarity            │
│  ③ Graph traversal — dependency chain walking               │
│                                                             │
│  Impact analysis on every query:                             │
│  "load_config" → 2 direct dependents, risk score: 50%       │
└────────────────────────────────────────────────────────────┘
```

**Why this eliminates context windows:**

| Scenario | Traditional Agent | Dong AI |
|----------|------------------|---------|
| Phase 5 needs Phase 1 code | Scroll through 50K of conversation history | Query graph → get `def load_config(path: str) -> dict` |
| Refactor a function | Hope the model remembers all callers | Query graph → get dependency tree + impact score |
| Resume project after 1 week | Start over | Load checkpoint → inject graph context → continue |
| Merge two projects | Impossible | `dong graph merge project-a project-b` |
| LLM context usage | 20K-50K per call (history) | 1K-2K per call (precision context) |

**The result:** Context usage drops from 20K-50K to 1K-2K per LLM call. 64K windows become comfortable. 256K becomes overkill. This is not "bigger context" — it's **no more context window problem**.

### 🏢 Persistent Personal Company Memory

Every project, every design decision, every function signature, every lesson learned — **permanently stored and cross-referenceable**.

```
dong graph list
  配置系统:   4 符号 (2 函数, 1 类)  1 依赖
  小说世界:   2 符号 (0 函数, 0 类)  0 依赖
  erp系统:    8 符号 (3 函数, 3 类)  4 依赖
  API审计:   15 符号 (6 函数, 4 类)  9 依赖
```

- **Cross-project memory**: Projects don't exist in isolation. Symbols from one project can be referenced by another. The graph database spans your entire work history.
- **Decision traceability**: Every board review score, every design rationale, every rejection reason — stored and queryable. Not "we decided X" but "we decided X because Y scored 8.5 vs Z scored 6.2."
- **Resume any project**: `dong run --resume` loads checkpoint + graph context. Walk away for a week, come back, and the system remembers not just what was built but why it was built that way.
- **Merge knowledge bases**: `dong graph merge from_project to_project` combines two independent graph memories into one. Build a utility library in one project, then merge it into your main project's memory.

### 🚀 Ultra-Large Project Engineering

Dong AI is designed for projects that span weeks, hundreds of files, and multiple phases — the kind of work where every other AI system breaks down.

**Pipeline generation:** The CEO identifies project type (software/novel/game/analysis/audit) and generates a custom execution pipeline via LLM. Software projects get scaffold→core→test→release. Novels get world-building→outline→write→revise. Each pipeline is purpose-built, not templated.

**Multi-phase coherence:** Phase gates enforce quality before the next phase starts. But more importantly, graph memory ensures Phase 12 can reference decisions made in Phase 2 with exact precision — not through a degraded conversation history, but through directly querying the indexed decision.

**Requirement traceability lock:** The design phase produces a checklist of verifiable requirements. Each subsequent task is checked against it. Missing requirements deduct from the phase score. The report at project end shows exactly which requirements were met and which were not — with evidence.

**Practical results from real use:**
- A configuration management system: CLI + YAML parser + schema validator + watcher daemon, ~1200 lines across 8 files, 42 tests, all passing
- Multi-phase architecture analysis: 14 phases, Phase 12 correctly referenced Phase 2 function signatures via graph memory
- Cross-project audit: Merged two codebases' graph memories into one, ran a unified audit across both

**Technology stack:** Pure Python. Zero external AI dependencies. 121 tests. 20+ model providers with automatic failover. Runs on CPU, GPU, cloud API, or any combination. MIT license.

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
  <sub>Not a chatbot — your AI workforce.</sub><br>
  <sub><a href="https://github.com/Dong04-123/Dong-AI-Company">Dong AI Company</a></sub>
</div>

---

## Acknowledgements

- **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** — Dong AI scans `~/.hermes/skills/` for skill integration.
- **[MCP Protocol](https://modelcontextprotocol.io)** — Dong AI implements the MCP client for tool discovery and invocation.
