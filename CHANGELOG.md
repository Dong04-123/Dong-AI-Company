# Changelog

## 0.1.0 (2026-06-06)

### 🚀 Features

- **CEO Governance Pipeline**: Red/blue team debate → dynamic worker pool → board review → phase gates
- **Graph Memory**: Cross-project symbol/dependency persistence with semantic search
- **Experience Engine**: Project debrief → skill extraction → recall injection. CEO learns from past work
- **20 Model Providers**: DeepSeek, OpenAI, Claude, Gemini, Groq, Together, local llama.cpp, Ollama, and more — auto failover
- **11 Agent Tools**: web_search, web_fetch, browser_navigate, browser_screenshot, read/write/list files, run commands, memory, graph_query
- **Dynamic Pipeline Generation**: CEO uses LLM to design per-project execution pipelines
- **Project Type Detection**: Auto-classifies software/novel/game/analysis/audit projects
- **Requirement Traceability**: Design → requirements → phase gate coverage check

### 🏢 Enterprise

- **Bearer Token Auth**: API key authentication with multi-tenancy
- **Rate Limiting**: Per-tenant token bucket, configurable, Retry-After headers
- **Prometheus Metrics**: /metrics endpoint with request counts, latency histograms, error tracking
- **Structured Logging**: JSONL format, daily rotation, 30-day retention
- **Deep Health Check**: Provider ping, disk space, active key stats
- **Graceful Shutdown**: SIGTERM handling, resource cleanup
- **Docker**: Multi-stage build, non-root user, HEALTHCHECK

### 🔌 SDK & Ecosystem

- **TypeScript SDK (@dong-ai/sdk)**: ESM + CJS dual build, typed errors (7 types), exponential backoff retry, rate-limit header tracking, React hooks, 48 tests
- **Plugin Registry**: 8 built-in MCP plugins (filesystem, github, puppeteer, web-search, memory, sequential-thinking)
- **Hermes Skill**: 21 tools across 9 categories
- **REST API**: OpenAI-compatible chat completions (stream + non-stream), CEO run, webhooks
- **14 CLI Commands**: chat, run, serve, config, key (create/list/revoke), plugin (install/search/list), session, graph, cron, webhook, detect, setup

### 📚 Documentation

- README with badges, feature table, architecture diagram
- CONTRIBUTING.md with project structure, test patterns, PR checklist
- docs/architecture.md — system architecture
- docs/guide.md — user guide
- SECURITY.md — vulnerability reporting
- CODE_OF_CONDUCT.md
- 4 runnable examples in examples/

### ✅ Quality

- 281 Python tests, all pass in ~5s, pure mock (no real API calls)
- 48 TypeScript tests
- 95% type annotation coverage (282/296 functions)
- ESM + CJS dual build for TypeScript SDK
- No circular dependencies
- TestClient-tested API endpoints
