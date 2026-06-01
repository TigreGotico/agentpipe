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

**Claude** — runs `claude auth status --json`, parses `loggedIn`, `email`, `authMethod`, `subscriptionType`.

**Gemini** — checks `gemini --version` for auth, then probes with a test prompt to detect rate limits and extract reset time from the error message.

**OpenCode** — runs `opencode providers list` for auth, `opencode models` for available models, `opencode stats --models` for usage stats. Accepts `"opencode"`, `"opencode-free"`, `"opencode-zen"`, and `"opencode-go"` as provider names.

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
- `provider` (str) — the provider name
- `rate_limited` (bool) — whether this looks like a rate-limit error
- `resets_in_seconds` (int or None) — seconds until the rate limit resets (parsed from error message)

Recognizes rate-limit patterns for:
- **Gemini** — `"You have exhausted your capacity on this model. Your quota will reset after Xs"`
- **OpenCode** — `"rate limit"`, `"quota exceeded"`, `"capacity"`, `"too many requests"` in stderr
- **Claude** — `"rate limit"` or `"overloaded"` in stderr

## Session Management

### List Sessions

```python
agent = Agent("gemini")
sessions = await agent.list_sessions()
for s in sessions:
    print(s.session_id, s.title, s.created_at, s.provider)
```

Supported for Gemini and OpenCode (all variants). Claude does not support session listing.

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