# agentpipe

Async Python wrapper for coding agent CLIs (Aider, Claude Code, Gemini, Kilo Code, OpenCode, QoderCLI, Vibe). Zero dependencies. Python 3.10+.

**Pages:**

- **[A Free OpenAI-Compatible Endpoint](free-llm-endpoint.md)** : zero to a working free LLM endpoint with docker, and behind ovos-persona-server
- **[Getting Started](getting-started.md)** : Install, prerequisites, 30-second quickstart, all features
- **[Providers and Models](providers.md)** : Provider aliases, OpenCode Free/Zen/Go, model tier map
- **[Core API](core-api.md)** : Agent, generation methods, sessions, events, results, new features
- **[Pipeline Functions](pipelines.md)** : fan_out, delegate, retry_until, map_concurrent
- **[Model Cascade](cascade.md)** : Fallback system, profiles, tiers, CLI runner
- **[HTTP Server (FastAPI)](server.md)** : Multi-agent HTTP API with OpenAI-compatible endpoint, persistent sessions, Docker
- **[MCP and Approval Modes](mcp-approval.md)** : MCP servers (inline + programmatic), approval modes, budget caps
- **[Auth and Quota](auth-quota.md)** : Auth login/logout, quota, rate limits, session management, MCP management, extensions, doctor
- **[Provider Internals](provider-internals.md)** : Provider protocol, classes, command building, event parsing
- **[Advanced Usage](advanced.md)** : Custom executors, error handling, framework integration
- **[Feature Matrix](feature-matrix.md)** : Full per-provider feature comparison, effort mapping, approval modes
- **[API Reference](api-reference.md)** : Full import list, defaults, dataclass fields, method signatures