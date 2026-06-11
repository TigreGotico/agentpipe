# Pipeline Functions

agentpipe provides pipeline functions for composing agents, plus a batch API
for running many independent prompts (dataset creation).

## fan_out

Run multiple prompts through the **same agent** concurrently (semaphore-capped):

```python
from agentpipe import Agent, fan_out

agent = Agent("gemini")
results: list[str] = await fan_out(
    agent,
    ["Summarize file A", "Summarize file B", "Summarize file C"],
    max_concurrency=3,  # semaphore limit (default 5)
    cwd=".",
    timeout=120,
)
# results = ["summary of A", "summary of B", "summary of C"]
```

**Signature:**
```python
async def fan_out(
    agent: Agent,
    prompts: Sequence[str],
    *,
    max_concurrency: int = 5,
    cwd: str | None = None,
    timeout: int = 300,
    return_exceptions: bool = False,
) -> list[str | BaseException]
```

Returns one string per prompt, in the same order as the input. With
`return_exceptions=True` a failed prompt yields its exception in place
instead of aborting the whole batch.

## delegate

Draft with one agent, then review with another:

```python
from agentpipe import Agent, delegate

drafter = Agent("opencode-free")   # cheap/fast for drafting
reviewer = Agent("claude-sonnet")  # strong for review

final: str = await delegate(
    drafter,
    reviewer,
    "Write a unit test for this function",
    "Review for correctness and edge cases",  # optional review prompt
)
```

The reviewer receives the drafter's output prepended to the review prompt. If no review prompt is given, a default review instruction is used.

**Signature:**
```python
async def delegate(
    drafter: Agent,
    reviewer: Agent,
    draft_prompt: str,
    review_prompt: str | None = None,
    *,
    cwd: str | None = None,
    timeout: int = 300,
) -> str
```

## retry_until

Keep retrying until a validator function passes:

```python
from agentpipe import Agent, retry_until

agent = Agent("opencode-zen")
result: str = await retry_until(
    agent,
    "Fix all lint errors in this file",
    validator=lambda text: "no errors" in text.lower(),
    max_attempts=3,
    refine_prompt="The result still has errors. Fix them.",
)
```

How it works:
1. Call `agent.generate(prompt)`.
2. If `validator(result)` returns `True`, return the result.
3. If `False`, call again — if `refine_prompt` is set, the previous output + refine prompt is prepended; otherwise the original prompt is retried.
4. Repeat up to `max_attempts`.

**Signature:**
```python
async def retry_until(
    agent: Agent,
    prompt: str,
    *,
    validator: Callable[[str], bool],
    max_attempts: int = 3,
    refine_prompt: str | None = None,
    cwd: str | None = None,
    timeout: int = 300,
) -> str
```

## map_concurrent

Send the **same prompt** to multiple agents concurrently:

```python
from agentpipe import Agent, map_concurrent

agents = [Agent("claude-sonnet"), Agent("gemini-pro"), Agent("opencode-zen")]
results: list[str] = await map_concurrent(agents, "Explain quantum computing in one paragraph")
# One response per agent
```

**Signature:**
```python
async def map_concurrent(
    agents: Sequence[Agent],
    prompt: str,
    *,
    max_concurrency: int = 5,
    cwd: str | None = None,
    timeout: int = 300,
    return_exceptions: bool = False,
) -> list[str | BaseException]
```

Returns one string per agent, in the same order as the input list. With
`return_exceptions=True` a failed agent yields its exception in place.

## run_batch / iter_batch

Run many **independent** prompts with bounded concurrency. Unlike `fan_out`,
every prompt produces a `BatchItem` whether it succeeded or failed — built for
dataset creation, where one bad item must not sink a thousand-prompt run.

```python
from agentpipe import Agent, run_batch

items = await run_batch(
    ["Translate 'hello' to PT", "Translate 'world' to PT"],
    agent=Agent("opencode-free"),   # omit to use the model cascade per prompt
    max_concurrency=4,
    max_retries=1,
)
for item in items:                  # input order
    if item.ok:
        print(item.id, item.text)
    else:
        print(item.id, "FAILED:", item.error)
```

Prompts can be strings, `(id, prompt)` tuples, or dicts with `prompt`/`id`
keys. When no `agent` is given, each prompt goes through the
[model cascade](cascade.md) (`models`/`profile` arguments), so rate-limited
free models fall back automatically.

`iter_batch` is the streaming variant — an async iterator that yields each
`BatchItem` as it completes (out of order; each item carries its `index`),
which is what the [`agentpipe batch` CLI](cli.md) uses to write results
incrementally. `skip_ids` skips already-answered items (resume support).

**BatchItem fields:** `index`, `id`, `prompt`, `text`, `error`, `provider`,
`model`, `duration_seconds`, `cost_usd`, `input_tokens`, `output_tokens`,
plus the `ok` property and `to_dict()` for JSON serialization.