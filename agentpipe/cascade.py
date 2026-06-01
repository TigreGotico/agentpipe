"""Model cascade — try models in priority order, fall back on rate limits or errors.

The core idea: define tiers of models (free → cheap → mid → premium),
try each in sequence, and automatically fall back when a model is rate-limited,
overloaded, or errors out. Tracks cost and latency across attempts.

Usage:

    from agentpipe.cascade import cascade, ModelTier, CASCADE_PROFILES

    # Default: start free, escalate on failure
    result = await cascade("Write a unit test for this function")

    # Coding profile: prioritize coding-capable models
    result = await cascade("Refactor this module", profile="coding")

    # Custom order
    result = await cascade(
        "Explain this architecture",
        models=["opencode/big-pickle", "gemini-2.5-flash", "opencode/kimi-k2.5"],
    )

    # Access attempt history
    for attempt in result.attempts:
        print(f"{attempt.model}: {'OK' if attempt.success else attempt.error_type}")
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from ._agent import Agent
from ._executor import AgentProcessError
from ._quota import parse_rate_limit_error

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ._types import GenerationResult


class ModelTier(int, Enum):
    FREE = 0
    CHEAP = 1
    MID = 2
    PREMIUM = 3


class ErrorType(str, Enum):
    RATE_LIMIT = "rate_limit"
    PROCESS_ERROR = "process_error"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class CascadeAttempt:
    model: str
    provider: str
    success: bool
    error_type: ErrorType | None = None
    error_message: str | None = None
    rate_limit_resets_in: int | None = None
    cost_usd: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0
    result_text: str | None = None


@dataclass
class CascadeResult:
    text: str
    attempts: list[CascadeAttempt] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    successful_model: str | None = None
    successful_provider: str | None = None

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def failed_attempts(self) -> list[CascadeAttempt]:
        return [a for a in self.attempts if not a.success]

    @property
    def rate_limited_models(self) -> list[str]:
        return [a.model for a in self.attempts if a.error_type == ErrorType.RATE_LIMIT]


CASCADE_PROFILES: dict[str, list[str]] = {
    "default": [
        "opencode/big-pickle",
        "gemini-2.5-flash",
        "opencode/gemini-3-flash",
        "opencode/deepseek-v4-flash-free",
        "opencode/mimo-v2.5-free",
        "opencode/nemotron-3-super-free",
        "opencode/kimi-k2.5",
        "opencode/minimax-m2.5",
    ],
    "coding": [
        "opencode/big-pickle",
        "opencode/deepseek-v4-flash-free",
        "opencode-gemini-3-flash-via-opencode",
        "gemini-2.5-flash",
        "opencode/deepseek-v4-flash",
        "opencode/kimi-k2.6",
        "opencode-go/deepseek-v4-flash",
        "opencode/minimax-m2.7",
    ],
    "reasoning": [
        "opencode/kimi-k2.6",
        "opencode/glm-5.1",
        "opencode/minimax-m2.7",
        "opencode/glm-5",
        "opencode/minimax-m2.5",
        "gemini-2.5-flash",
        "opencode/big-pickle",
    ],
    "fast-free": [
        "opencode/big-pickle",
        "gemini-2.5-flash",
        "opencode/gemini-3-flash",
        "opencode/deepseek-v4-flash-free",
    ],
    "free-only": [
        "opencode/big-pickle",
        "opencode/deepseek-v4-flash-free",
        "opencode/gemini-3-flash",
        "gemini-2.5-flash",
        "opencode/mimo-v2.5-free",
        "opencode/nemotron-3-super-free",
    ],
}

MODEL_TIER_MAP: dict[str, ModelTier] = {
    "opencode/big-pickle": ModelTier.FREE,
    "gemini-2.5-flash": ModelTier.FREE,
    "opencode/gemini-3-flash": ModelTier.FREE,
    "opencode/deepseek-v4-flash-free": ModelTier.FREE,
    "opencode/mimo-v2.5-free": ModelTier.FREE,
    "opencode/nemotron-3-super-free": ModelTier.FREE,
    "opencode/minimax-m3-free": ModelTier.FREE,
    "opencode/kimi-k2.5": ModelTier.CHEAP,
    "opencode/minimax-m2.5": ModelTier.CHEAP,
    "opencode-go/deepseek-v4-flash": ModelTier.CHEAP,
    "opencode/kimi-k2.6": ModelTier.MID,
    "opencode/minimax-m2.7": ModelTier.MID,
    "opencode/glm-5": ModelTier.MID,
    "opencode/glm-5.1": ModelTier.MID,
    "opencode-go/glm-5.1": ModelTier.MID,
    "opencode/gpt-5": ModelTier.PREMIUM,
    "opencode/qwen3.6-plus": ModelTier.PREMIUM,
    "opencode/qwen3.5-plus": ModelTier.PREMIUM,
    "opencode/gemini-3.1-pro": ModelTier.PREMIUM,
}

MODEL_PROVIDER_MAP: dict[str, str] = {
    "gemini-2.5-flash": "gemini",
    "gemini-2.5-pro": "gemini",
}


def _resolve_provider(model: str) -> str:
    if model in MODEL_PROVIDER_MAP:
        return MODEL_PROVIDER_MAP[model]
    if model.startswith("opencode-go/"):
        return "opencode"
    if model.startswith("opencode/"):
        return "opencode"
    raise ValueError(f"Cannot determine provider for model '{model}'")


def _model_tier(model: str) -> ModelTier:
    return MODEL_TIER_MAP.get(model, ModelTier.MID)


async def cascade(
    prompt: str,
    *,
    models: Sequence[str] | None = None,
    profile: str = "default",
    max_tier: ModelTier | None = None,
    max_attempts: int = 10,
    max_cost_usd: float | None = None,
    max_total_seconds: float | None = None,
    per_attempt_timeout: int = 120,
    retry_delay_seconds: float = 2.0,
    rate_limit_backoff_seconds: int = 10,
    cwd: str = "/tmp",
    on_attempt: callable | None = None,
) -> CascadeResult:
    """Try models in priority order, falling back on errors or rate limits.

    Args:
        prompt: The prompt to send.
        models: Explicit model order. Overrides profile.
        profile: Named profile from CASCADE_PROFILES. Default: "default".
        max_tier: Stop escalating beyond this tier. None = no limit.
        max_attempts: Maximum number of models to try. Default: 10.
        max_cost_usd: Stop if cumulative cost exceeds this. None = no limit.
        max_total_seconds: Stop if cumulative wall time exceeds this. None = no limit.
        per_attempt_timeout: Timeout per individual model call in seconds.
        retry_delay_seconds: Brief pause between attempts. Default: 2s.
        rate_limit_backoff_seconds: Pause after hitting a rate limit. Default: 10s.
        cwd: Working directory for all attempts. Default: /tmp.
        on_attempt: Optional callback(attempt: CascadeAttempt) called after each attempt.

    Returns:
        CascadeResult with the text from the first successful attempt,
        plus full history of all attempts made.
    """
    model_list = list(models) if models is not None else CASCADE_PROFILES.get(profile, CASCADE_PROFILES["default"])

    if max_tier is not None:
        model_list = [m for m in model_list if _model_tier(m).value <= max_tier.value]

    model_list = model_list[:max_attempts]

    attempts: list[CascadeAttempt] = []
    total_cost = 0.0
    start_time = time.monotonic()

    for model in model_list:
        provider = _resolve_provider(model)

        if max_cost_usd is not None and total_cost > max_cost_usd:
            break

        if max_total_seconds is not None and (time.monotonic() - start_time) > max_total_seconds:
            break

        attempt_start = time.monotonic()
        attempt = CascadeAttempt(model=model, provider=provider, success=False)

        try:
            agent = Agent(provider, model=model, cwd=cwd, timeout=per_attempt_timeout)
            result: GenerationResult = await agent.generate_full(prompt)

            attempt.success = True
            attempt.result_text = result.text
            attempt.duration_seconds = time.monotonic() - attempt_start

            if result.usage is not None:
                attempt.cost_usd = result.usage.cost_usd
                attempt.input_tokens = result.usage.input_tokens
                attempt.output_tokens = result.usage.output_tokens
                if result.usage.cost_usd is not None:
                    total_cost += result.usage.cost_usd

            attempts.append(attempt)
            if on_attempt:
                on_attempt(attempt)

            return CascadeResult(
                text=result.text,
                attempts=attempts,
                total_cost_usd=total_cost,
                total_duration_seconds=time.monotonic() - start_time,
                successful_model=model,
                successful_provider=provider,
            )

        except AgentProcessError as e:
            attempt.duration_seconds = time.monotonic() - attempt_start
            rate_info = parse_rate_limit_error(provider, e)

            if rate_info["rate_limited"]:
                attempt.error_type = ErrorType.RATE_LIMIT
                attempt.rate_limit_resets_in = rate_info.get("resets_in_seconds")
                attempt.error_message = e.stderr[:200] if e.stderr else "rate limited"
                attempts.append(attempt)
                if on_attempt:
                    on_attempt(attempt)

                backoff = rate_info.get("resets_in_seconds") or rate_limit_backoff_seconds
                await asyncio.sleep(min(backoff, rate_limit_backoff_seconds))
                continue

            attempt.error_type = ErrorType.PROCESS_ERROR
            attempt.error_message = str(e)[:200]
            attempts.append(attempt)
            if on_attempt:
                on_attempt(attempt)

            await asyncio.sleep(retry_delay_seconds)
            continue

        except asyncio.TimeoutError:
            attempt.duration_seconds = time.monotonic() - attempt_start
            attempt.error_type = ErrorType.TIMEOUT
            attempt.error_message = f"timed out after {per_attempt_timeout}s"
            attempts.append(attempt)
            if on_attempt:
                on_attempt(attempt)

            await asyncio.sleep(retry_delay_seconds)
            continue

        except Exception as e:
            attempt.duration_seconds = time.monotonic() - attempt_start
            attempt.error_type = ErrorType.UNKNOWN
            attempt.error_message = f"{type(e).__name__}: {str(e)[:200]}"
            attempts.append(attempt)
            if on_attempt:
                on_attempt(attempt)

            await asyncio.sleep(retry_delay_seconds)
            continue

    all_failed = [a for a in attempts if not a.success]
    error_summary = "; ".join(f"{a.model}: {a.error_type}" for a in all_failed[:5])
    raise RuntimeError(
        f"All {len(attempts)} models failed. Errors: {error_summary}. Tried: {', '.join(a.model for a in attempts)}"
    )


async def cascade_coding(
    prompt: str,
    *,
    max_tier: ModelTier = ModelTier.CHEAP,
    **kwargs,
) -> CascadeResult:
    """Convenience: cascade with the 'coding' profile, stopping at cheap tier."""
    return await cascade(prompt, profile="coding", max_tier=max_tier, **kwargs)


async def cascade_fast_free(
    prompt: str,
    **kwargs,
) -> CascadeResult:
    """Convenience: cascade with only free, fast models."""
    return await cascade(prompt, profile="fast-free", **kwargs)


async def cascade_free_only(
    prompt: str,
    **kwargs,
) -> CascadeResult:
    """Convenience: cascade with only free models (no cost)."""
    return await cascade(prompt, profile="free-only", **kwargs)


def tier_summary() -> dict[ModelTier, list[dict]]:
    """Return a summary of all known models organized by tier."""
    result: dict[ModelTier, list[dict]] = {tier: [] for tier in ModelTier}
    for model, tier in sorted(MODEL_TIER_MAP.items(), key=lambda x: (x[1].value, x[0])):
        provider = _resolve_provider(model)
        result[tier].append(
            {
                "model": model,
                "provider": provider,
                "tier": tier,
            }
        )
    return result
