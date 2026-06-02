# agentpipe — Multi-Agent Delegation Skill

Use agentpipe when you (the primary coding agent) need to delegate work to
cheaper or specialized agents running locally. Instead of doing everything
yourself at your own cost, offload grunt work to free-tier agents.

## When to use this skill

| Situation | Do this |
|-----------|---------|
| Writing boilerplate tests | Delegate to `opencode-free` or `kilo` |
| Linting / fixing style | Delegate to `aider --lint` |
| Drafting docs | Delegate to `gemini-flash` |
| Parallel code review | Fan out to `aider` + `kilo` simultaneously |
| You hit a rate limit | Cascade to a cheaper/backup model |

## How to use it

### 1. Install agentpipe

```bash
pip install agentpipe
```

You also need at least one provider CLI installed locally (see README).

### 2. Delegate a task

Write a temporary Python script that imports agentpipe, runs the delegation,
prints the result, and exits:

```python
# /tmp/delegate_write_test.py
import asyncio
from agentpipe import Agent

async def main():
    agent = Agent("kilo")  # free
    result = await agent.generate(
        "Write a pytest test suite for src/parser.py. "
        "Cover happy path, edge cases, and error handling."
    )
    print(result)

asyncio.run(main())
```

```bash
python /tmp/delegate_write_test.py
```

### 3. Fan-out for parallelism

```python
import asyncio
from agentpipe import fan_out, Agent

async def main():
    results = await fan_out(
        Agent("aider", timeout=60),
        [
            "Review api/routes.py for security issues",
            "Review src/db.py for SQL injection",
            "Review tests/ for coverage gaps",
        ],
        max_concurrency=3,
    )
    for r in results:
        print(r)

asyncio.run(main())
```

### 4. Cascade: try free first, escalate to you

```python
import asyncio
from agentpipe import cascade

async def main():
    result = await cascade(
        "Refactor this function to be async",
        profile="default",       # free → cheap → mid
        max_cost_usd=0.05,
    )
    print(result.text)

asyncio.run(main())
```

## Recommended delegation patterns

| Your task | Delegate to | Why |
|-----------|-------------|-----|
| "Write unit tests" | `kilo` or `opencode-free` | Free, fast |
| "Fix lint errors" | `aider --lint` | Built-in lint fix |
| "Draft README" | `gemini-flash` | Fast, free |
| "Explain this code" | `aider` or `kilo` | Cheap |
| "Review for bugs" | `claude-sonnet` or `gemini-pro` | Smart but expensive — use sparingly |
| "Generate 10 examples" | `fan_out(kilo, [...], max_concurrency=5)` | Parallel free workers |

## Cost awareness

- `kilo/kilo-auto/free` — $0
- `opencode/big-pickle` — $0
- `aider` with OpenRouter free models — $0
- `gemini-flash` — free tier (15 RPM)
- `claude/haiku` — cheap (~$0.25/M input)
- `claude/sonnet` — moderate (~$3/M input)
- `claude/opus` — expensive (~$15/M input)

Always prefer free agents for grunt work. Reserve expensive agents for
architecture decisions, security reviews, and complex refactoring that
cheap models get wrong.
