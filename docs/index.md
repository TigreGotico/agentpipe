# agentpipe

Async Python wrapper for coding agent CLIs (Claude Code, Gemini, Opencode). Zero dependencies. Python 3.10+.

**Pages:**

- **[Getting Started](getting-started.md)** — Install, prerequisites, 30-second quickstart
- **[Providers and Models](providers.md)** — Provider aliases, OpenCode Free/Zen/Go, model tier map
- **[Core API](core-api.md)** — Agent, generation methods, sessions, events, results
- **[Pipeline Functions](pipelines.md)** — fan_out, delegate, retry_until, map_concurrent
- **[Model Cascade](cascade.md)** — Fallback system, profiles, tiers, CLI runner
- **[MCP and Approval Modes](mcp-approval.md)** — MCP servers, approval modes, budget caps
- **[Auth and Quota](auth-quota.md)** — check_quota, rate limits, session management
- **[Provider Internals](provider-internals.md)** — Provider protocol, classes, command building, event parsing
- **[Advanced Usage](advanced.md)** — Custom executors, error handling, framework integration
- **[Feature Matrix](feature-matrix.md)** — Per-provider feature comparison
- **[API Reference](api-reference.md)** — Full import list, defaults, dataclass fields