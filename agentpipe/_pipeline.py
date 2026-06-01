from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from ._agent import Agent


async def fan_out(
    agent: Agent,
    prompts: Sequence[str],
    *,
    max_concurrency: int = 5,
    cwd: str | None = None,
    timeout: int = 300,
) -> list[str]:
    sem = asyncio.Semaphore(max_concurrency)
    results: list[str] = [None] * len(prompts)  # type: ignore[list-item]

    async def _run(idx: int, prompt: str) -> None:
        async with sem:
            session = agent.session(cwd=cwd, timeout=timeout)
            results[idx] = await session.generate(prompt)

    await asyncio.gather(*(_run(i, p) for i, p in enumerate(prompts)))
    return results


async def delegate(
    drafter: Agent,
    reviewer: Agent,
    draft_prompt: str,
    review_prompt: str | None = None,
    *,
    cwd: str | None = None,
    timeout: int = 300,
) -> str:
    draft_session = drafter.session(cwd=cwd, timeout=timeout)
    draft = await draft_session.generate(draft_prompt)

    if review_prompt is None:
        review_prompt = f"Review and improve the following:\n\n{draft}"
    else:
        review_prompt = f"{review_prompt}\n\n---\n\n{draft}"

    review_session = reviewer.session(cwd=cwd, timeout=timeout)
    return await review_session.generate(review_prompt)


async def retry_until(
    agent: Agent,
    prompt: str,
    *,
    validator: Callable[[str], bool],
    max_attempts: int = 3,
    refine_prompt: str | None = None,
    cwd: str | None = None,
    timeout: int = 300,
) -> str:
    session = agent.session(cwd=cwd, timeout=timeout)
    result = await session.generate(prompt)

    for _attempt in range(1, max_attempts):
        if validator(result):
            return result
        follow_up = refine_prompt or "The previous result was not satisfactory. Please try again, fixing any issues."
        result = await session.generate(follow_up)

    return result


async def map_concurrent(
    agents: Sequence[Agent],
    prompt: str,
    *,
    cwd: str | None = None,
    timeout: int = 300,
) -> list[str]:
    async def _run(agent: Agent) -> str:
        session = agent.session(cwd=cwd, timeout=timeout)
        return await session.generate(prompt)

    return list(await asyncio.gather(*(_run(a) for a in agents)))
