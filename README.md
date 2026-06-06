<div align="center">

```
██████╗  ██████╗ ███╗   ██╗ ██████╗     █████╗ ██╗
██╔══██╗██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗██║
██║  ██║██║   ██║██╔██╗ ██║██║         ███████║██║
██║  ██║██║   ██║██║╚██╗██║██║         ██╔══██║██║
██████╔╝╚██████╔╝██║ ╚████║╚██████╗    ██║  ██║██║
╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝    ╚═╝  ╚═╝╚═╝
```

# Dong AI Company

**Cross-project memory and organizational governance for AI agents.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/Dong04-123/Dong-AI-Company/ci.yml?branch=main&label=CI)](.github/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-281%20passed-brightgreen)](tests/)
[![Providers](https://img.shields.io/badge/providers-20%2B-orange)](src/dong_ai/model_pool.py)
[![PyPI](https://img.shields.io/pypi/v/dong-ai)](https://pypi.org/project/dong-ai/)

```bash
pip install dong-ai
dong setup
dong make "a quarterly market analysis"
```

</div>

---

## The Problem

Every AI agent works in a vacuum. Close a conversation, lose the context. Start a new
project, the model has no memory of last week's architecture decisions. Long-running
projects degrade into incoherence as the window fills with noise.

Dong AI solves this by adding two missing layers to any agent:

1. **Cross-project indexed memory** — every symbol, decision, and dependency is stored in
   a queryable graph that persists across sessions. The model fetches what it needs
   instead of scrolling through degraded history.
2. **Organizational governance** — red/blue debate before design decisions, dynamic worker
   recruitment per task, board review with quality gates, and automated post-project
   debrief that extracts lessons for future work.

The result: agents that remember what they built, why they built it that way, and improve
with every project.

---

## Quick Start

```bash
pip install dong-ai        # zero external AI deps
dong setup                  # detect hardware, configure providers
dong make "a CLI tool for CSV parsing"
```

No API key required to start — `dong check` shows available options.

### All Commands

| Command | Use |
|---------|-----|
| `dong make "request"` | Self-directed execution for any domain |
| `dong run "request"` | Full governance pipeline (debate → workers → review) |
| `dong quick "task"` | Lightweight mode, no pipeline overhead |
| `dong analyze <path> 'question'` | Read and analyze any source file |
| `dong edit <path> 'instruction'` | Edit file with diff preview |
| `dong debug` | CI failure root cause analysis |
| `dong company start --domain "..." --duration 8h` | Background company runtime |
| `dong company status` | View running company state |
| `dong company knowledge` | Organizational metacognition map |
| `dong company review` | Decision audit trail |
| `dong graph list` | List indexed graph projects |
| `dong graph view <id>` | Drill into a project's symbols and dependencies |
| `dong detect` | Full system status |
| `dong serve` | OpenAI-compatible API server |
| `dong update` | Upgrade from PyPI |

---

## How It Works

```
Any Agent (CLI / Hermes / Claude Code / Cursor / Copilot)
  │  shell out: dong <command>
  │
  ▼
Dong AI Engine
  │
  ├── Column Memory          5-slot context management (C0-C4) with unloading
  ├── Graph Memory           Persistent symbol/dependency/decision index
  ├── Experience Engine      Post-project debrief → skill extraction → future recall
  ├── SafetyGovernor         Confidence scoring, risk budgets, confirmation gates
  ├── Metacognition          Knowledge map, strategy evolution, improvement tracking
  └── Domain Runtimes        7x24 background operation for monitoring tasks
```

### Column Memory

Not "infinite context" — precise context. Five named columns with independent token
budgets:

| Column | Content | Reason to keep |
|--------|---------|----------------|
| C0 | Project goal, constraints, user | Always available |
| C1 | Symbol signatures, API contracts | Reference surface |
| C2 | Dependency maps, architecture | Navigation |
| C3 | Active decisions, rationale | Traceability |
| C4 | Historical context, past output | Full when room |

When the budget is tight, C4 is unloaded first. The model always has the current goal,
available symbols, and recent decisions — without wading through 50K of conversation
history.

### Graph Memory

Every project run indexes its symbols, dependencies, and decisions into an SQLite graph.
Three retrieval methods:

- **Keyword match** — exact signature lookup
- **Semantic search** — embedding cosine similarity
- **Graph traversal** — dependency chain walking

Impact analysis on every query: `load_config → 2 callers, risk score: 50%`.

Projects don't exist in isolation. Symbols from one project can be referenced by another.
Cross-project queries work across your entire work history.

### Governance Pipeline

```
User Request
  │
  ├── CEO — type detection, pipeline generation, worker recruitment
  ├── Design — red/blue team debate, requirements extraction, coverage checklist
  ├── Execute — dynamic workers, parallel execution, self-healing (×3), cross-review
  ├── Board — phase scoring (1-10), minimum gate 6.0, requirement audit
  ├── Debrief — lesson extraction → Experience Engine
  └── Report — full evidence trail
```

No hardcoded roles. Each task generates its own specialist team via LLM — software
projects get architects and engineers, novels get world-builders and writers, audits
get security analysts.

---

## Capabilities

| Category | Description |
|----------|-------------|
| **Project execution** | Three modes: `make` (self-directed research→execute), `run` (full governance), `quick` (lightweight) |
| **Code workflow** | `analyze` (code Q&A), `edit` (diff-preview edits), `debug` (CI root cause from GitHub Actions) |
| **Company runtime** | 7x24 background domains, configurable duration, hourly health checks, daily reports |
| **Metacognition** | Knowledge map of domain expertise, learning strategy effectiveness, knowledge gaps |
| **Governance** | Confidence scoring, risk budgets, confirmation gates, decision audit trail |
| **Context** | 5-column memory management, cross-project graph memory, session recovery |
| **Plugins** | MCP ecosystem integration, plugin registry |
| **Models** | 20+ providers with automatic failover, local GGUF support, custom provider config |
| **API** | OpenAI-compatible server, webhook subscriptions, scheduled cron tasks |

---

## Why Not Just Use a Bigger Context Window?

Larger windows don't solve the structural problem — the model still has to search through
noise to find signal, and the window is reset when the conversation ends.

Dong AI's approach is orthogonal: **index instead of remember**. A 1K-2K precision query
replaces 50K of degraded context. Cross-session persistence replaces per-session
ephemeral state. This works regardless of window size — 64K, 128K, or 1M.

---

## Integration

Dong AI is designed to be called from any agent that can run shell commands.

| Agent | Method |
|-------|--------|
| **Hermes Agent** | `cp SKILL.md ~/.hermes/skills/dong-ai-company/` |
| **Claude Code** | `cp CLAUDE.md ~/.claude/claude.md` |
| **Cursor** | `cp .cursorrules .cursorrules` |
| **GitHub Copilot** | `.github/copilot-instructions.md` |
| **Any** | `dong <command>` from shell |

Adapter files are maintained at [Dong04-123/Dong-AI-skill](https://github.com/Dong04-123/Dong-AI-skill).

---

## Testing

```bash
pip install pytest
pytest tests/
# 281 tests, ~2s, zero external deps, no network calls, no API keys
```

---

## Project Status

Active development. v0.1.x — core pipeline, column memory, experience engine, governance,
company runtime, and multi-agent adapters are functional. Breaking changes possible until
v1.0.

---

## License

MIT — free for personal, research, and commercial use. Attribution required.

---

<div align="center">
  <a href="https://github.com/Dong04-123/Dong-AI-Company">Engine</a>
  ·
  <a href="https://pypi.org/project/dong-ai/">PyPI</a>
  ·
  <a href="https://github.com/Dong04-123/Dong-AI-skill">Adapters</a>
  ·
  <a href="https://github.com/NousResearch/hermes-agent">Hermes Agent</a>
</div>
