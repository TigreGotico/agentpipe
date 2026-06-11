"""Batch generation — run many independent prompts with bounded concurrency.

Built for dataset creation: every prompt becomes a `BatchItem` whether it
succeeded or failed, so one bad item never sinks the run. Items can be plain
strings, ``(id, prompt)`` tuples, or dicts with ``prompt``/``id`` keys.

Usage:

    from agentpipe import Agent, run_batch

    items = await run_batch(prompts, agent=Agent("opencode-free"), max_concurrency=4)
    rows = [i.to_dict() for i in items if i.ok]

    # Or stream completions as they finish (for incremental writes):
    async for item in iter_batch(prompts, profile="free-only"):
        out.write(json.dumps(item.to_dict()) + "\n")

When no agent is given, each prompt goes through the model cascade
(``models``/``profile``), so rate-limited models fall back automatically.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from .cascade import cascade

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence

    from ._agent import Agent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchItem:
    """Outcome of one prompt in a batch. Exactly one of text/error is set."""

    index: int
    id: str
    prompt: str
    text: str | None = None
    error: str | None = None
    provider: str | None = None
    model: str | None = None
    duration_seconds: float = 0.0
    cost_usd: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def _normalize_prompts(prompts: Sequence) -> list[tuple[str, str]]:
    """Normalize mixed prompt inputs to (id, prompt) pairs."""
    pairs: list[tuple[str, str]] = []
    for idx, item in enumerate(prompts):
        if isinstance(item, str):
            pairs.append((str(idx), item))
        elif isinstance(item, dict):
            prompt = item.get("prompt")
            if not prompt:
                raise ValueError(f"Prompt dict at index {idx} has no 'prompt' key: {item}")
            pairs.append((str(item.get("id", idx)), prompt))
        else:
            item_id, prompt = item
            pairs.append((str(item_id), prompt))
    return pairs


async def _run_one(
    index: int,
    item_id: str,
    prompt: str,
    *,
    agent: Agent | None,
    models: Sequence[str] | None,
    profile: str,
    timeout: int,
    cwd: str | None,
    max_retries: int,
) -> BatchItem:
    last_error: str | None = None
    start = time.monotonic()
    for attempt in range(max_retries + 1):
        try:
            if agent is not None:
                result = await agent.generate_full(prompt, cwd=cwd, timeout=timeout)
                usage = result.usage
                return BatchItem(
                    index=index,
                    id=item_id,
                    prompt=prompt,
                    text=result.text,
                    provider=agent.provider,
                    model=agent.model,
                    duration_seconds=time.monotonic() - start,
                    cost_usd=usage.cost_usd if usage else None,
                    input_tokens=usage.input_tokens if usage else 0,
                    output_tokens=usage.output_tokens if usage else 0,
                )
            cascade_result = await cascade(
                prompt,
                models=models,
                profile=profile,
                per_attempt_timeout=timeout,
                cwd=cwd or "/tmp",
            )
            return BatchItem(
                index=index,
                id=item_id,
                prompt=prompt,
                text=cascade_result.text,
                provider=cascade_result.successful_provider,
                model=cascade_result.successful_model,
                duration_seconds=time.monotonic() - start,
                cost_usd=cascade_result.total_cost_usd or None,
            )
        except Exception as e:
            last_error = f"{type(e).__name__}: {str(e)[:300]}"
            logger.warning(
                "batch item '%s' failed (attempt %d/%d): %s",
                item_id,
                attempt + 1,
                max_retries + 1,
                last_error,
            )
    return BatchItem(
        index=index,
        id=item_id,
        prompt=prompt,
        error=last_error,
        duration_seconds=time.monotonic() - start,
    )


async def iter_batch(
    prompts: Sequence,
    *,
    agent: Agent | None = None,
    models: Sequence[str] | None = None,
    profile: str = "default",
    max_concurrency: int = 4,
    timeout: int = 300,
    cwd: str | None = None,
    max_retries: int = 0,
    skip_ids: set[str] | None = None,
) -> AsyncIterator[BatchItem]:
    """Yield BatchItems as they complete (out of order; each carries its index).

    Args:
        prompts: Strings, (id, prompt) tuples, or dicts with prompt/id keys.
        agent: Run every prompt on this agent (fresh session per prompt).
            When None, each prompt goes through the model cascade instead.
        models: Explicit cascade model order (cascade mode only).
        profile: Cascade profile name (cascade mode only). Default: "default".
        max_concurrency: Maximum prompts in flight at once. Default: 4.
        timeout: Per-prompt timeout in seconds (per cascade attempt in cascade mode).
        cwd: Working directory for the agent processes.
        max_retries: Extra attempts per failed item before recording the error.
        skip_ids: Item ids to skip entirely (resume support).
    """
    pairs = _normalize_prompts(prompts)
    if skip_ids:
        pairs_indexed = [(i, pid, p) for i, (pid, p) in enumerate(pairs) if pid not in skip_ids]
    else:
        pairs_indexed = [(i, pid, p) for i, (pid, p) in enumerate(pairs)]

    sem = asyncio.Semaphore(max_concurrency)

    async def _guarded(index: int, item_id: str, prompt: str) -> BatchItem:
        async with sem:
            return await _run_one(
                index,
                item_id,
                prompt,
                agent=agent,
                models=models,
                profile=profile,
                timeout=timeout,
                cwd=cwd,
                max_retries=max_retries,
            )

    tasks = [asyncio.create_task(_guarded(i, pid, p)) for i, pid, p in pairs_indexed]
    try:
        for future in asyncio.as_completed(tasks):
            yield await future
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()


async def run_batch(
    prompts: Sequence,
    *,
    agent: Agent | None = None,
    models: Sequence[str] | None = None,
    profile: str = "default",
    max_concurrency: int = 4,
    timeout: int = 300,
    cwd: str | None = None,
    max_retries: int = 0,
    skip_ids: set[str] | None = None,
    on_result: Callable[[BatchItem], None] | None = None,
) -> list[BatchItem]:
    """Run all prompts and return BatchItems in input order.

    Same arguments as `iter_batch`, plus `on_result` — an optional callback
    fired as each item completes (e.g. progress reporting).
    """
    items: list[BatchItem] = []
    async for item in iter_batch(
        prompts,
        agent=agent,
        models=models,
        profile=profile,
        max_concurrency=max_concurrency,
        timeout=timeout,
        cwd=cwd,
        max_retries=max_retries,
        skip_ids=skip_ids,
    ):
        items.append(item)
        if on_result is not None:
            try:
                on_result(item)
            except Exception as e:
                logger.warning("on_result callback raised %s: %s", type(e).__name__, e)
    items.sort(key=lambda i: i.index)
    return items
