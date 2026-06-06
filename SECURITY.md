# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Active development |

## Reporting a Vulnerability

Vulnerabilities can be reported via:

1. **GitHub Issues** — Create an issue with the `security` label (public)
2. **Email** — hanxudong1234@gmail.com

We aim to respond within 48 hours and release a fix within 7 days for confirmed vulnerabilities.

## Scope

The following are in scope:
- Remote code execution via crafted prompts
- API authentication bypass
- Unauthorized data access through graph memory
- Provider credential leakage

The following are out of scope:
- Prompt injection (inherent to LLM systems)
- Model-level vulnerabilities (third-party providers)
- Social engineering
