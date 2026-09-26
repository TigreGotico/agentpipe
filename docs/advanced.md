# Advanced Usage

## Custom Executors

`Agent` accepts an `executor` parameter for dependency injection:

```python
from agentpipe import Agent, AsyncSubprocessExecutor

executor = AsyncSubprocessExecutor()
agent = Agent("claude", executor=executor)
```

This is useful for testing (mock the executor) or for sharing a single executor instance across multiple agents.

### Writing Tests with Mocked Executors

In unit tests, mock `AgentSession.generate_full` at the class level:

```python
from unittest.mock import AsyncMock, patch
from agentpipe import Agent, AgentSession

async def test_my_agent():
    async def mock_generate(self_session, prompt, **kwargs):
        return GenerationResult(text="mocked response", session_id="test", returncode=0)

    with patch.object(AgentSession, "generate_full", mock_generate):
        agent = Agent("gemini")
        result = await agent.generate_full("test prompt")
        assert result.text == "mocked response"
```

For pipeline tests, mock at the same level:

```python
from agentpipe import fan_out, delegate

async def test_fan_out():
    with patch.object(AgentSession, "generate_full", new_callable=AsyncMock) as mock:
        mock.return_value = GenerationResult(text="result", session_id="s1", returncode=0)
        results = await fan_out(Agent("claude"), ["a", "b", "c"])
        assert results == ["result", "result", "result"]
```

## Error Handling

### AgentProcessError

```python
from agentpipe import Agent, AgentProcessError

agent = Agent("gemini")

try:
    result = await agent.generate("hello")
except AgentProcessError as e:
    print(f"Process exited with code {e.returncode}")
    print(f"stderr: {e.stderr}")
    print(f"argv: {e.argv}")
```

`AgentProcessError` extends `RuntimeError` with:
- `returncode: int`: the process exit code
- `stderr: str`: stderr output
- `argv: list[str]`: the command that was run

### Cascade Error Handling

The cascade system catches `AgentProcessError`, `asyncio.TimeoutError`, and generic exceptions, classifying each attempt:

| Exception | ErrorType | What happens |
|---|---|---|
| `AgentProcessError` with rate-limit pattern | `RATE_LIMIT` | Back off, then try next model |
| `AgentProcessError` (other) | `PROCESS_ERROR` | Try next model |
| `asyncio.TimeoutError` | `TIMEOUT` | Try next model |
| Any other exception | `UNKNOWN` | Try next model |

If all models fail, `cascade()` raises `RuntimeError` with a summary of all attempts.

### Timeout Control

```python
# Per-agent timeout (default 300s)
agent = Agent("claude", timeout=60)
result = await agent.generate("quick question")

# Per-call override
result = await agent.generate("quick question", timeout=30)
```

## Integrating with Other Frameworks

agentpipe has zero dependencies and uses only `asyncio.create_subprocess_exec`. It works alongside any async framework.

### FastAPI

```python
from fastapi import FastAPI
from agentpipe import cascade_free_only

app = FastAPI()

@app.get("/ask")
async def ask(q: str):
    result = await cascade_free_only(q, per_attempt_timeout=30)
    return {"answer": result.text, "model": result.successful_model}
```

### Background Workers

```python
import asyncio
from agentpipe import Agent

async def worker(prompt: str):
    agent = Agent("opencode-free", timeout=120)
    result = await agent.generate(prompt)
    return result

# Run multiple prompts concurrently
results = await asyncio.gather(
    worker("prompt 1"),
    worker("prompt 2"),
    worker("prompt 3"),
)
```

### Logging Cascade Attempts

```python
import logging
from agentpipe import cascade, CascadeAttempt

logger = logging.getLogger(__name__)

def log_attempt(attempt: CascadeAttempt):
    if attempt.success:
        logger.info(f"ok {attempt.model} ({attempt.provider}): {attempt.duration_seconds:.1f}s")
    else:
        logger.warning(f"fail {attempt.model} ({attempt.provider}): {attempt.error_type} - {attempt.error_message}")

result = await cascade("important prompt", on_attempt=log_attempt, profile="default")
logger.info(f"Success: {result.successful_model} via {result.successful_provider}")
```

### Cost-Aware Pipelines

```python
from agentpipe import Agent, delegate, cascade

# Draft with a free model, review with a cheap one
result = await delegate(
    Agent("opencode-free"),  # free drafting
    Agent("opencode-zen"),   # cheap review
    "Write a migration script",
    "Review for SQL injection and data loss",
)

# Or cascade with a hard cost cap
result = await cascade(
    "Optimize this query",
    profile="coding",
    max_cost_usd=0.10,  # never spend more than 10 cents
    on_attempt=lambda a: print(f"  {a.model}: ${a.cost_usd or 0:.4f}"),
)
```

---
[← Provider Internals](provider-internals.md) · [Home](index.md) · [Feature Matrix →](feature-matrix.md)