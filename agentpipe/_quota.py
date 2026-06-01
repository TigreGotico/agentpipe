from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ._agent import _PROVIDER_MAP, DEFAULT_MODELS
from ._executor import AgentProcessError, AsyncSubprocessExecutor
from ._types import CommandSpec

_CLAUDE_PLAN_LIMITS: dict[str, dict] = {
    "max": {"requests_per_day": None, "context_window": 200000, "tier": "max"},
    "pro": {"requests_per_day": None, "context_window": 200000, "tier": "pro"},
    "free": {"requests_per_day": None, "context_window": 200000, "tier": "free"},
}

_GEMINI_RATE_LIMIT_PATTERN = re.compile(
    r"You have exhausted your capacity on this model\. Your quota will reset after (\d+)s",
    re.IGNORECASE,
)

_GEMINI_RATE_LIMIT_SECONDS_PATTERN = re.compile(r"quota will reset after (\d+)s", re.IGNORECASE)

_RATE_LIMIT_PATTERN = re.compile(
    r"(rate limit|quota exceeded|capacity|too many requests)",
    re.IGNORECASE,
)


@dataclass
class QuotaStatus:
    authenticated: bool = False
    subscription_type: str | None = None
    email: str | None = None
    plan_limits: dict = field(default_factory=dict)
    rate_limited: bool = False
    rate_limit_resets_in_seconds: int | None = None
    available_models: list[str] = field(default_factory=list)
    usage_stats: dict = field(default_factory=dict)
    provider: str | None = None
    raw_auth: dict | None = None
    raw_error: str | None = None


async def check_quota(
    provider: str | None = None,
    *,
    model: str | None = None,
    executor: AsyncSubprocessExecutor | None = None,
) -> QuotaStatus:
    executor = executor or AsyncSubprocessExecutor()
    effective_provider = provider or "claude"
    if effective_provider not in _PROVIDER_MAP:
        available = ", ".join(sorted(_PROVIDER_MAP.keys()))
        raise ValueError(f"Unknown provider '{effective_provider}'. Available: {available}")

    prov = _PROVIDER_MAP[effective_provider](model=model or DEFAULT_MODELS.get(effective_provider))

    if effective_provider == "claude":
        return await _claude_quota_status(prov, executor)
    if effective_provider == "gemini":
        return await _gemini_quota_status(prov, executor)
    if effective_provider in ("opencode", "opencode-free", "opencode-zen", "opencode-go"):
        return await _opencode_quota_status(prov, executor)

    return QuotaStatus(provider=effective_provider)


async def _claude_quota_status(provider: object, executor: AsyncSubprocessExecutor) -> QuotaStatus:
    spec = CommandSpec(
        argv=[provider.binary_name, "auth", "status", "--json"],
        stdin="",
        env=provider.build_env(),
        timeout=15.0,
    )
    try:
        stdout, _stderr = await executor.run(spec)
        data = json.loads(stdout)
        sub_type = data.get("subscriptionType", "unknown")
        plan_limits = _CLAUDE_PLAN_LIMITS.get(sub_type, {})
        return QuotaStatus(
            authenticated=data.get("loggedIn", False),
            subscription_type=sub_type,
            email=data.get("email"),
            plan_limits=plan_limits,
            provider="claude",
            raw_auth=data,
        )
    except (AgentProcessError, json.JSONDecodeError, Exception) as e:
        return QuotaStatus(
            authenticated=False,
            provider="claude",
            rate_limited=False,
            raw_error=str(e),
        )


async def _gemini_quota_status(provider: object, executor: AsyncSubprocessExecutor) -> QuotaStatus:
    env = provider.build_env()
    spec = CommandSpec(
        argv=[provider.binary_name, "--version"],
        stdin="",
        env=env,
        timeout=10.0,
    )
    authenticated = False
    try:
        await executor.run(spec)
        authenticated = True
    except AgentProcessError:
        pass

    rate_limited = False
    resets_in = None
    model = provider.model or "gemini-2.5-flash"
    test_spec = CommandSpec(
        argv=[provider.binary_name, "-y", "--model", model, "-p", "test", "-o", "stream-json"],
        stdin="",
        env=env,
        cwd="/tmp",
        timeout=30.0,
    )
    try:
        stdout, stderr = await executor.run(test_spec)
        if stderr:
            match = _GEMINI_RATE_LIMIT_SECONDS_PATTERN.search(stderr)
            if match:
                rate_limited = True
                resets_in = int(match.group(1))
    except AgentProcessError as e:
        if e.stderr and _GEMINI_RATE_LIMIT_PATTERN.search(e.stderr):
            rate_limited = True
            match = _GEMINI_RATE_LIMIT_SECONDS_PATTERN.search(e.stderr)
            if match:
                resets_in = int(match.group(1))

    return QuotaStatus(
        authenticated=authenticated,
        rate_limited=rate_limited,
        rate_limit_resets_in_seconds=resets_in,
        provider="gemini",
    )


async def _opencode_quota_status(provider: object, executor: AsyncSubprocessExecutor) -> QuotaStatus:
    env = provider.build_env()
    authenticated = False
    try:
        auth_spec = CommandSpec(
            argv=[provider.binary_name, "providers", "list"],
            stdin="",
            env=env,
            timeout=15.0,
        )
        stdout, _stderr = await executor.run(auth_spec)
        authenticated = len(stdout.strip()) > 0
    except AgentProcessError:
        pass

    models: list[str] = []
    try:
        models_spec = CommandSpec(
            argv=[provider.binary_name, "models"],
            stdin="",
            env=env,
            timeout=30.0,
        )
        stdout, _stderr = await executor.run(models_spec)
        models = [line.strip() for line in stdout.strip().splitlines() if line.strip()]
    except AgentProcessError:
        pass

    usage_stats: dict = {}
    try:
        stats_spec = CommandSpec(
            argv=[provider.binary_name, "stats", "--models"],
            stdin="",
            env=env,
            timeout=15.0,
        )
        stdout, _stderr = await executor.run(stats_spec)
        usage_stats = {"raw": stdout}
    except AgentProcessError:
        pass

    return QuotaStatus(
        authenticated=authenticated,
        available_models=models,
        usage_stats=usage_stats,
        provider="opencode",
    )


def parse_rate_limit_error(provider: str, error: AgentProcessError) -> dict:
    info: dict = {"provider": provider, "rate_limited": False, "resets_in_seconds": None}

    if provider == "gemini":
        match = _GEMINI_RATE_LIMIT_SECONDS_PATTERN.search(error.stderr or "")
        if match:
            info["rate_limited"] = True
            info["resets_in_seconds"] = int(match.group(1))
            return info
        if _GEMINI_RATE_LIMIT_PATTERN.search(error.stderr or ""):
            info["rate_limited"] = True
            return info

    if (provider == "opencode" or provider.startswith("opencode-")) and _RATE_LIMIT_PATTERN.search(error.stderr or ""):
        info["rate_limited"] = True
        return info

    if provider == "claude" and (
        "rate limit" in (error.stderr or "").lower() or "overloaded" in (error.stderr or "").lower()
    ):
        info["rate_limited"] = True
        return info

    return info
