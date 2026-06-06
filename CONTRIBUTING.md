# Contributing to Dong AI Company

Thanks for your interest! Dong AI is an open-source AI Company Agent framework. This guide covers how to contribute effectively.

## Quick Start

```bash
# Clone and install
git clone https://github.com/Dong04-123/Dong-AI-Company.git
cd Dong-AI-Company
pip install -e .
pip install -e '.[server,all]'

# Run tests
python3 -m pytest tests/
```

## Project Structure

```
src/dong_ai/
├── ceo.py              # CEO coordinator — project lifecycle
├── design_engine.py    # Design phase with requirement extraction
├── worker.py           # Worker pool — parallel agent execution
├── experience_engine.py# Project debrief → skill → recall
├── tool_executor.py    # Agent tool system (search, file, browser)
├── datastore.py        # SQLite storage + graph memory
├── ceo_memory.py       # CEO memory (soul, facts, sessions)
├── model_pool.py       # 20-provider model router + failover
├── llm.py              # Pure HTTP LLM client
├── api.py              # FastAPI server with auth/rate-limit/metrics
├── cli.py              # CLI (14 commands)
├── tui.py              # Terminal UI
├── key_manager.py      # API key management
├── rate_limiter.py     # Token-bucket rate limiting
├── plugin_registry.py  # MCP plugin market (8 built-in)
├── mcp_client.py       # MCP protocol client
├── logger.py           # Structured JSONL logging
└── web_search.py       # DuckDuckGo search (zero deps)
```

## Architecture

```
CEO ──→ DesignEngine ──→ WorkerPool ──→ BoardReview
  │                          │
  ├── ExperienceEngine ──────┘  (debrief → recall)
  ├── Graph Memory              (cross-project persistence)
  └── ToolExecutor              (web_search, web_fetch, file ops)
```

Layer rules:
- `llm.py` imports nothing from `dong_ai` — pure HTTP
- `model_pool.py` imports from `llm.py` only
- Business logic (`ceo`, `worker`, `tui`) imports from `model_pool` or `llm`
- Tests never hit real APIs — pure mock

## Testing

**281 tests, all pure mock, ~5s.** No real API calls, no network.

```bash
# Run all
python3 -m pytest tests/

# Single file
python3 -m pytest tests/test_experience_engine.py -v

# Fast (no api.py tests which need TestClient)
python3 -m pytest tests/ --ignore=tests/test_api.py
```

Key test fixtures (in `tests/conftest.py`):
- `mock_llm` — keyword-driven LLM simulator (earliest-position matching)
- `temp_dir` — isolated filesystem per test
- `isolated_datastore` — fresh Datastore singleton per test
- `mock_urlopen` — monkeypatches `urllib.request.urlopen`

## Pull Request Checklist

- [ ] Tests pass: `python3 -m pytest tests/ -q`
- [ ] No circular imports: `python3 -c "import dong_ai"` succeeds
- [ ] New code has test coverage
- [ ] Type annotations on all functions
- [ ] No hardcoded API endpoints or model names
- [ ] Uses `@patch` / `monkeypatch` for LLM/HTTP — never calls real APIs in tests

## Code Style

- Python 3.10+ with `from __future__ import annotations`
- Type annotations on ALL functions (no bare `def foo():`)
- Prints for user-facing output, `logger` for internal events
- No external dependencies for core features
- `do_xxx` methods in `ToolExecutor` for agent tools

## Adding a Model Provider

Edit `model_pool.py` — add an entry to the `PROVIDERS` dict:

```python
"my-provider": {
    "name": "My Provider",
    "base_url": "https://api.example.com/v1",
    "env_key": "MY_API_KEY",
    "models": ["my-model"],
    "provider_type": "openai",
},
```

Only `openai` provider_type is supported (OpenAI-compatible HTTP API).

## License

MIT — see LICENSE.
