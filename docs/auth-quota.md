# Auth, Quota, and Rate Limits

## check_quota

Check authentication status, subscription type, rate limits, and available models for each provider:

```python
from agentpipe import check_quota

# Check each provider
for provider in ["claude", "gemini", "opencode", "opencode-go"]:
    status = await check_quota(provider)
    print(f"{provider}:")
    print(f"  authenticated:  {status.authenticated}")
    print(f"  subscription:   {status.subscription_type}")
    print(f"  rate_limited:   {status.rate_limited}")
    print(f"  resets_in:      {status.rate_limit_resets_in_seconds}s")
    print(f"  models:         {len(status.available_models)}")
    print(f"  usage_stats:    {status.usage_stats}")
```

### QuotaStatus Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `authenticated` | `bool` | `False` | Whether the CLI is authenticated |
| `subscription_type` | `str | None` | `None` | e.g. `"max"`, `"pro"`, `"free"` |
| `email` | `str | None` | `None` | Account email (Claude only) |
| `plan_limits` | `dict` | `{}` | Per-plan limits (Claude) |
| `rate_limited` | `bool` | `False` | Whether currently rate-limited |
| `rate_limit_resets_in_seconds` | `int | None` | `None` | Seconds until rate limit resets |
| `available_models` | `list[str]` | `[]` | Models returned by `opencode models` |
| `usage_stats` | `dict` | `{}` | Raw usage stats (OpenCode) |
| `provider` | `str | None` | `None` | Provider name |
| `raw_auth` | `dict | None` | `None` | Raw auth response |
| `raw_error` | `str | None` | `None` | Error message if check failed |

### Provider-Specific Behavior

Claude runs `claude auth status --json` and parses `loggedIn`, `email`, `authMethod`, and `subscriptionType`.

Gemini checks `gemini --version` for auth, then probes with a test prompt to detect rate limits and read the reset time from the error message.

OpenCode runs `opencode providers list` for auth, `opencode models` for available models, and `opencode stats --models` for usage stats. It accepts `"opencode"`, `"opencode-free"`, `"opencode-zen"`, and `"opencode-go"` as provider names.

## parse_rate_limit_error

Extract structured rate-limit info from a caught `AgentProcessError`:

```python
from agentpipe import parse_rate_limit_error, AgentProcessError

try:
    result = await agent.generate("hello")
except AgentProcessError as e:
    info = parse_rate_limit_error("gemini", e)
    if info["rate_limited"]:
        print(f"Rate limited! Resets in {info['resets_in_seconds']}s")
```

Returns a dict with:
- `provider` (str): the provider name
- `rate_limited` (bool): whether this looks like a rate-limit error
- `resets_in_seconds` (int or None): seconds until the rate limit resets, parsed from the error message

Recognizes rate-limit patterns for:
- Gemini: `"You have exhausted your capacity on this model. Your quota will reset after Xs"`
- OpenCode: `"rate limit"`, `"quota exceeded"`, `"capacity"`, `"too many requests"` in stderr
- Claude: `"rate limit"` or `"overloaded"` in stderr

## Auth Methods

### Login and Logout

```python
from agentpipe import Agent

agent = Agent("claude")

# Check auth status
status = await agent.auth_status()
print(status.authenticated, status.email)

# Login (Claude, OpenCode)
status = await agent.auth_login()
# For Claude with method:
status = await agent.auth_login(method="api_key")

# Logout (Claude, OpenCode)
status = await agent.auth_logout()
```

| Provider | `auth_login()` | `auth_logout()` | `auth_status()` |
|----------|---------------|----------------|-----------------|
| Claude | `claude auth login` | `claude auth logout` | `claude auth status --json` |
| Gemini | Not supported | Not supported | `gemini --version` check |
| OpenCode | `opencode providers login` | `opencode providers logout` | `opencode providers list` |

## Session Management

### List Sessions

```python
agent = Agent("gemini")
sessions = await agent.list_sessions()
for s in sessions:
    print(s.session_id, s.title, s.created_at, s.provider)
```

Supported for Gemini and OpenCode (all variants). Claude does not support session listing.

### Delete Session

```python
agent = Agent("opencode")
deleted = await agent.delete_session("session-id")
```

OpenCode only. Returns `True` if successful.

### Export Session

```python
agent = Agent("opencode")
export = await agent.export_session("session-id")
print(export.session_id)
print(export.data)    # JSON string
print(export.format)  # "json"
```

OpenCode only. Returns a `SessionExport` with the session data as JSON.

### Import Session

```python
agent = Agent("opencode")
new_id = await agent.import_session(json_data)
```

OpenCode only. Imports session data from a JSON string. Returns the new session ID or `None` on failure.

### List Models

```python
agent = Agent("opencode")
models = await agent.list_models()
for m in models:
    print(m.id, m.name, m.provider, m.context_window)
```

OpenCode only. Returns `list[ModelInfo]`.

### Stats

```python
agent = Agent("opencode")
stats = await agent.stats(days=7, cwd=".")
print(stats)  # {"raw": "..."}
```

OpenCode only. Passes `--days` if specified, returns raw output.

## MCP Management

### Add MCP Server

```python
from agentpipe import Agent

agent = Agent("claude")

# HTTP/SSE server (Claude, OpenCode)
await agent.mcp_add("docs", url="http://localhost:9000/sse")

# Stdio server (Claude, OpenCode)
await agent.mcp_add("github", command="npx", args=["-y", "@mcp/server-github"])

# With env vars (OpenCode)
await agent.mcp_add("github", command="npx", args=["-y", "@mcp/server-github"],
                     env={"GITHUB_TOKEN": "ghp_x"})

# With headers and scope (Claude only)
await agent.mcp_add("api", url="http://localhost:8080/sse",
                    headers={"Authorization": "Bearer tok"}, scope="project")
```

| Provider | `mcp_add(url=)` | `mcp_add(command=)` | `headers` | `env` | `scope` |
|----------|----------------|--------------------|-----------|-------|---------|
| Claude | `claude mcp add -t sse --url` | `claude mcp add -t stdio` | Yes | Yes | Yes |
| OpenCode | `opencode mcp add -t sse --url` | `opencode mcp add -t stdio` | No | Yes | No |

### Remove MCP Server

```python
await agent.mcp_remove("github")

# With scope (Claude only)
await agent.mcp_remove("github", scope="project")
```

### List MCP Servers

```python
servers = await agent.mcp_list()
for s in servers:
    print(s.name, s.type, s.url, s.command)
```

## Extensions (Gemini)

```python
agent = Agent("gemini")
extensions = await agent.list_extensions()
for ext in extensions:
    print(ext.name, ext.version, ext.enabled)
```

Gemini only.

## Doctor (Claude)

```python
agent = Agent("claude")
result = await agent.doctor()
print(result)  # {"raw": "..."}
```

Claude only.

---
[← MCP and Approval Modes](mcp-approval.md) · [Home](index.md) · [Provider Internals →](provider-internals.md)