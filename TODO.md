# agentpipe — TODO

## High priority

- [ ] Add GitHub remote and set up CI (pytest + ruff via [[gh-automations]] at `@dev`)
- [ ] Add provider unit tests (`tests/unit/providers/` — all three providers parse events correctly)
- [ ] Wire `generate_stream` to actually yield async iterator (currently returns coroutine, not iterator)
- [ ] Add live/integration test (`tests/live/`) guarded behind env flag for manual verification

## Medium

- [ ] Add `timeout` and `retry` kwargs to `Agent.generate` / `Agent.generate_full`
- [ ] Publish to PyPI (add `[project.urls]` and set up trusted publishing)
- [ ] Add provider: `codex` (Anthropic Codex CLI)
- [ ] Add provider: `qwen` (Alibaba's Qwen coding agent)
- [ ] Rate-limit / cost-tracker utility that wraps `Agent` and warns on spend

## Low / nice-to-have

- [ ] MCP-server registration support (inject MCP config before launch)
- [ ] Token-aware prompt truncation (fit prompt within model context window)
- [ ] `agentpipe[all]` extras meta-package that pulls `claude-code`, `opencode`, `gemini-cli`
- [ ] Write a concept page in the wiki comparing agentpipe vs [[agentshim]] vs raw CLI
