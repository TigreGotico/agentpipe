# Providers and Models

## Provider Aliases

Each provider has shortcuts that pre-fill the default model for a particular tier:

```python
from agentpipe import Agent

# Aider: open-source, CLI-first (free via OpenRouter free tier)
Agent("aider")            # model="openrouter/google/gemma-4-26b-a4b-it:free"  (AiderProvider)

# Claude family
Agent("claude")           # model="sonnet"    (ClaudeProvider)
Agent("claude-sonnet")    # model="sonnet"    (ClaudeSonnetProvider)
Agent("claude-haiku")     # model="haiku"    (ClaudeHaikuProvider)
Agent("claude-opus")      # model="opus"     (ClaudeOpusProvider)

# Gemini family
Agent("gemini")           # model="gemini-2.5-flash"  (GeminiProvider)
Agent("gemini-flash")     # model="gemini-2.5-flash"  (GeminiFlashProvider)
Agent("gemini-pro")       # model="gemini-2.5-pro"   (GeminiProProvider)

# Kilo Code: fork of OpenCode with free tier
Agent("kilo")             # model="kilo/kilo-auto/free"  (KiloProvider)

# OpenCode family: three plans
Agent("opencode")         # model="opencode/gemini-3-flash"  (OpencodeZenProvider)
Agent("opencode-free")    # model="opencode/big-pickle"      (OpencodeFreeProvider)
Agent("opencode-zen")     # model="opencode/gemini-3-flash"  (OpencodeZenProvider)
Agent("opencode-go")      # model="opencode-go/deepseek-v4-flash" (OpencodeGoProvider)

# QoderCLI
Agent("qoder")            # model=None (uses QoderCLI default)  (QoderProvider)

# Mistral Vibe
Agent("vibe")             # model="mistral-large-latest"  (VibeProvider)

# MimoCode (binary: mimo)
Agent("mimo")             # model="mimo/mimo-auto"  (MimocodeProvider)

# Antigravity (binary: agy)
Agent("antigravity")      # model="Gemini 3.5 Flash (Medium)"  (AntigravityProvider)
```

Override the model at any time:

```python
Agent("claude", model="opus")
Agent("opencode-go", model="opencode-go/kimi-k2.6")
```

## Default Models

| Provider Key | Class | Default Model |
|---|---|---|---|
| `aider` | `AiderProvider` | `openrouter/google/gemma-4-26b-a4b-it:free` |
| `claude` | `ClaudeProvider` | `sonnet` |
| `claude-sonnet` | `ClaudeSonnetProvider` | `sonnet` |
| `claude-haiku` | `ClaudeHaikuProvider` | `haiku` |
| `claude-opus` | `ClaudeOpusProvider` | `opus` |
| `gemini` | `GeminiProvider` | `gemini-2.5-flash` |
| `gemini-flash` | `GeminiFlashProvider` | `gemini-2.5-flash` |
| `gemini-pro` | `GeminiProProvider` | `gemini-2.5-pro` |
| `kilo` | `KiloProvider` | `kilo/kilo-auto/free` |
| `opencode` | `OpencodeZenProvider` | `opencode/gemini-3-flash` |
| `opencode-free` | `OpencodeFreeProvider` | `opencode/big-pickle` |
| `opencode-zen` | `OpencodeZenProvider` | `opencode/gemini-3-flash` |
| `opencode-go` | `OpencodeGoProvider` | `opencode-go/deepseek-v4-flash` |
| `qoder` | `QoderProvider` | *(uses QoderCLI default)* |
| `vibe` | `VibeProvider` | `mistral-large-latest` |
| `mimo` | `MimocodeProvider` | `mimo/mimo-auto` |
| `mimo-auto` | `MimocodeAutoProvider` | `mimo/mimo-auto` |
| `mimo-v2-pro` | `MimocodeV2ProProvider` | `xiaomi/mimo-v2.5-pro` |
| `mimo-v2-flash` | `MimocodeV2FlashProvider` | `xiaomi/mimo-v2-flash` |
| `antigravity` | `AntigravityProvider` | `Gemini 3.5 Flash (Medium)` |
| `antigravity-flash-medium` | `AntigravityFlashMediumProvider` | `Gemini 3.5 Flash (Medium)` |
| `antigravity-flash-high` | `AntigravityFlashHighProvider` | `Gemini 3.5 Flash (High)` |
| `antigravity-flash-low` | `AntigravityFlashLowProvider` | `Gemini 3.5 Flash (Low)` |
| `antigravity-pro-low` | `AntigravityProLowProvider` | `Gemini 3.1 Pro (Low)` |
| `antigravity-pro-high` | `AntigravityProHighProvider` | `Gemini 3.1 Pro (High)` |
| `antigravity-claude-sonnet` | `AntigravityClaudeSonnetProvider` | `Claude Sonnet 4.6 (Thinking)` |
| `antigravity-claude-opus` | `AntigravityClaudeOpusProvider` | `Claude Opus 4.6 (Thinking)` |
| `antigravity-gpt-oss` | `AntigravityGptOssProvider` | `GPT-OSS 120B (Medium)` |

The Antigravity and MimoCode CLIs (`agy`, `mimo`) are not in the docker image.
Install them yourself to use those providers.

## OpenCode Plans: Free / Zen / Go

OpenCode has three distinct plans with different API endpoints, billing, and rate limits:

| Plan | Provider | Endpoint | Billing | Default Model |
|------|----------|----------|---------|---------------|
| **Free** | `opencode-free` | `opencode.ai/zen/v1` | $0, free models only | `opencode/big-pickle` |
| **Zen** | `opencode-zen` | `opencode.ai/zen/v1` | Pay-as-you-go | `opencode/gemini-3-flash` |
| **Go** | `opencode-go` | `opencode.ai/zen/go/v1` | $5/$10 monthly subscription | `opencode-go/deepseek-v4-flash` |

Key differences:

- Free and Zen share the same API endpoint and API key. Free models (`big-pickle`, `gemini-3-flash`, `*-free` suffixes) cost $0. All other Zen models charge per token.
- Go is a separate subscription with its own endpoint (`/zen/go/v1`), per-model rate limits (200-31K requests per 5 hours), and flat monthly billing.
- The model prefix (`opencode/` vs `opencode-go/`) determines which endpoint is hit. Free and Zen both use `opencode/` prefix models. Go uses the `opencode-go/` prefix.
- All three plans use the same `opencode` binary. The model string routes the request.

```python
# Free: $0 cost, limited models
Agent("opencode-free")   # → big-pickle

# Zen: pay-as-you-go, full model catalog
Agent("opencode-zen")    # → gemini-3-flash

# Go: subscription, higher rate limits
Agent("opencode-go")     # → deepseek-v4-flash (Go endpoint)
```

The cascade system automatically routes models to the correct plan:
- Models in `_FREE_MODELS` → `opencode-free`
- `opencode-go/` prefixed models → `opencode-go`
- All other `opencode/` models → `opencode-zen`

## Model Tier Map

The cascade system classifies models into cost tiers. This controls escalation order and cost caps:

| Tier | Value | Models |
|------|-------|--------|
| **FREE** | 0 | `opencode/big-pickle`, `gemini-2.5-flash`, `opencode/gemini-3-flash`, `opencode/deepseek-v4-flash-free`, `opencode/mimo-v2.5-free`, `opencode/nemotron-3-super-free`, `opencode/minimax-m3-free` |
| **CHEAP** | 1 | `opencode/kimi-k2.5`, `opencode/minimax-m2.5`, `opencode-go/deepseek-v4-flash` |
| **MID** | 2 | `opencode/kimi-k2.6`, `opencode/minimax-m2.7`, `opencode/glm-5`, `opencode/glm-5.1`, `opencode-go/glm-5.1` |
| **PREMIUM** | 3 | `opencode/gpt-5`, `opencode/qwen3.6-plus`, `opencode/qwen3.5-plus`, `opencode/gemini-3.1-pro` |

Models not in the map default to `MID`.

```python
from agentpipe import ModelTier, tier_summary

summary = tier_summary()
# {ModelTier.FREE: [{'model': 'opencode/big-pickle', 'provider': 'opencode-free', 'tier': 0}, ...],
#  ModelTier.CHEAP: [...],
#  ModelTier.MID: [...],
#  ModelTier.PREMIUM: [...]}
```

---
[← Getting Started](getting-started.md) · [Home](index.md) · [Core API →](core-api.md)