# Model Cascade (Fallback)

The cascade system tries models in priority order, automatically falling back when a model is rate-limited, errors out, or times out. It tracks cost, latency, and per-attempt diagnostics.

## cascade()

```python
from agentpipe import cascade, CascadeResult

result: CascadeResult = await cascade(
    "Write a fast sorting algorithm",
    # Pick ONE of: models= or profile= (models overrides profile)
    models=["opencode/big-pickle", "gemini-2.5-flash", "opencode/kimi-k2.5"],
    profile="default",           # named profile from CASCADE_PROFILES
    max_tier=None,               # ModelTier — stop escalating beyond this tier
    max_attempts=10,             # max models to try (default 10)
    max_cost_usd=None,           # stop if cumulative cost exceeds this
    max_total_seconds=None,      # stop if wall time exceeds this
    per_attempt_timeout=120,     # seconds per model call (default 120)
    retry_delay_seconds=2.0,     # pause between failed attempts (default 2s)
    rate_limit_backoff_seconds=10, # pause after hitting rate limit (default 10s)
    cwd="/tmp",                  # working directory
    on_attempt=None,             # callback(CascadeAttempt) after each attempt
)
```

### CascadeResult

```python
result.text                    # str — output from the first successful model
result.successful_model        # str | None — e.g. "opencode/big-pickle"
result.successful_provider     # str | None — e.g. "opencode-free"
result.attempts                # list[CascadeAttempt] — full history
result.total_cost_usd          # float — cumulative cost across attempts
result.total_duration_seconds  # float — total wall time
result.attempt_count           # int
result.failed_attempts         # list[CascadeAttempt]
result.rate_limited_models     # list[str]
```

### CascadeAttempt

Each attempt in the history:

```python
attempt.model                 # str — model name
attempt.provider              # str — resolved provider (e.g. "opencode-free")
attempt.success               # bool
attempt.error_type             # ErrorType | None — RATE_LIMIT, PROCESS_ERROR, TIMEOUT, UNKNOWN
attempt.error_message          # str | None
attempt.rate_limit_resets_in   # int | None — seconds until rate limit resets
attempt.cost_usd               # float | None
attempt.input_tokens           # int
attempt.output_tokens          # int
attempt.duration_seconds       # float — wall time for this attempt
attempt.result_text             # str | None — output if success
```

### Error Handling

If **all** models fail, `cascade()` raises `RuntimeError` with a summary:

```python
try:
    result = await cascade("prompt", max_attempts=2)
except RuntimeError as e:
    print(e)  # "All 2 models failed. Errors: opencode/big-pickle: ErrorType.RATE_LIMIT; ..."
```

The four error types:

| ErrorType | Meaning |
|---|---|
| `RATE_LIMIT` | Provider returned a rate-limit error (cascade auto-backs off) |
| `PROCESS_ERROR` | Subprocess exited with non-zero code |
| `TIMEOUT` | Subprocess exceeded `per_attempt_timeout` |
| `UNKNOWN` | Any other exception |

## Cascade Profiles

Built-in profiles define model ordering:

| Profile | Models (in priority order) |
|---------|----------------------------|
| `default` | big-pickle → gemini-flash → gemini-3-flash → deepseek-free → mimo-free → nemotron-free → kimi-k2.5 → minimax-m2.5 |
| `coding` | big-pickle → deepseek-free → gemini-3-flash → gemini-flash → deepseek-v4-flash → kimi-k2.6 → go/deepseek-v4-flash → minimax-m2.7 |
| `reasoning` | kimi-k2.6 → glm-5.1 → minimax-m2.7 → glm-5 → minimax-m2.5 → gemini-flash → big-pickle |
| `fast-free` | big-pickle → gemini-flash → gemini-3-flash → deepseek-free |
| `free-only` | big-pickle → deepseek-free → gemini-3-flash → gemini-flash → mimo-free → nemotron-free |

```python
from agentpipe import CASCADE_PROFILES

# Access profiles directly
print(CASCADE_PROFILES["coding"])
```

## Tiers and Cost Control

```python
from agentpipe import cascade, ModelTier

# Only try FREE and CHEAP models
result = await cascade("prompt", max_tier=ModelTier.CHEAP)

# Only try FREE models (zero cost guaranteed)
result = await cascade("prompt", max_tier=ModelTier.FREE)

# Stop if cumulative cost exceeds $0.50
result = await cascade("prompt", max_cost_usd=0.50)

# Stop if wall time exceeds 60 seconds
result = await cascade("prompt", max_total_seconds=60)
```

Combine constraints for tight control:

```python
result = await cascade(
    "Quick question",
    profile="free-only",
    max_tier=ModelTier.FREE,
    max_cost_usd=0.01,        # effectively free
    max_attempts=3,            # don't try more than 3 models
    per_attempt_timeout=30,    # 30s per model
)
```

## Convenience Functions

```python
from agentpipe import cascade_coding, cascade_fast_free, cascade_free_only

# Coding-optimized profile, stops at CHEAP tier
result = await cascade_coding("Write tests for foo.py")

# Fast free models only
result = await cascade_fast_free("Quick question")

# All free models, no cost
result = await cascade_free_only("Explain this concept")
```

| Function | Profile | Default `max_tier` |
|---|---|---|
| `cascade_coding()` | `"coding"` | `CHEAP` |
| `cascade_fast_free()` | `"fast-free"` | None (all) |
| `cascade_free_only()` | `"free-only"` | None (all) |

## on_attempt Callback

Track progress in real time:

```python
def log_attempt(attempt):
    status = "✓" if attempt.success else f"✗ {attempt.error_type}"
    print(f"  {attempt.model} ({attempt.provider}): {status} [{attempt.duration_seconds:.1f}s]")

result = await cascade("prompt", on_attempt=log_attempt)
# Output:
#   opencode/big-pickle (opencode-free): ✗ RATE_LIMIT [2.1s]
#   gemini-2.5-flash (gemini): ✓ [4.5s]
```

## CLI Runner

```bash
# Basic usage
python -m agentpipe.cascade_run "Write a unit test for this function"

# Choose a profile
python -m agentpipe.cascade_run --profile coding "Refactor this module"

# Explicit model list (overrides profile)
python -m agentpipe.cascade_run --models "opencode/big-pickle,gemini-2.5-flash" "Summarize"

# Free models only
python -m agentpipe.cascade_run --free-only "Quick question"

# Tier cap and cost control
python -m agentpipe.cascade_run --max-tier cheap --max-cost 0.50 "Prompt"

# Per-attempt timeout and max attempts
python -m agentpipe.cascade_run --timeout 60 --max-attempts 3 "Quick question"

# JSON output (for piping)
python -m agentpipe.cascade_run --json "Explain this architecture"
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `prompt` | *(required)* | The prompt to send |
| `--profile` | `default` | Named profile from CASCADE_PROFILES |
| `--models` | None | Comma-separated model list (overrides profile) |
| `--free-only` | False | Only try free models |
| `--max-tier` | None | Stop escalating beyond this tier (free/cheap/mid/premium) |
| `--max-attempts` | 10 | Max models to try |
| `--max-cost` | None | Stop if cumulative cost exceeds $USD |
| `--timeout` | 120 | Per-attempt timeout in seconds |
| `--cwd` | `/tmp` | Working directory |
| `--json` | False | Output result as JSON |