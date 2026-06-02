# agentpipe — Multi-Agent Delegation Skill

Use agentpipe when you (the primary coding agent) need to delegate work to
cheaper or specialized agents running locally. Instead of doing everything
yourself at your own cost, offload grunt work to free-tier agents.

## Setup per coding agent

agentpipe is not a plugin — it's a Python library you call from scripts.
Each coding agent needs to know agentpipe exists and how to invoke it.

### Claude Code

Add to `CLAUDE.md` at the project root:

```markdown
## agentpipe — delegation

You can delegate grunt work to free/cheap agents via agentpipe.
Write a temp Python script, run it, capture the output:

```python
import asyncio
from agentpipe import Agent
result = await Agent("kilo").generate("Write tests for src/parser.py")
print(result)
```

Run with:
```bash
python /tmp/delegate.py
```

See `SKILL.md` for full delegation patterns and cost awareness.
```

### OpenCode

Add to `AGENTS.md` at the project root — this file is already present.
OpenCode reads it at startup. The agent will know agentpipe is available
and can write delegation scripts on demand.

### Gemini CLI

Gemini reads `GEMINI.md` or `.gemini/instructions.md` from the project
root. Add:

```markdown
You can delegate to other coding agents via agentpipe.
Write a Python script, run it, read the output.
See SKILL.md for delegation patterns.
```

### Cursor

Cursor reads `.cursorrules` at the project root. Add:

```markdown
You can delegate tasks to free/cheap agents via agentpipe (Python lib).
Write a temporary script, run it with `python /tmp/delegate.py`,
and use the output. See SKILL.md for patterns and cost info.
```

### Continue.dev

Continue reads `.continuerules` at the project root. Add:

```markdown
agentpipe is available for multi-agent delegation.
Write a temp Python script, execute it, return the result.
See SKILL.md for usage.
```

### GitHub Copilot

Copilot reads `.github/copilot-instructions.md`. Add:

```markdown
You can use agentpipe to delegate work to other coding agents.
Write a Python script that imports agentpipe, runs a task, prints result.
```

### Aider

Aider reads `.aider.md` if present. Add:

```markdown
Use agentpipe to delegate subtasks to other coding agents.
Write a temp Python script, run it, use the output.
```

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

## HTTP Server with OpenAI-compatible endpoint

The FastAPI server includes an OpenAI-compatible `/v1/chat/completions` endpoint
so **any tool that speaks the OpenAI API** (Cursor, Continue.dev, any
OpenAI SDK) can be pointed at agentpipe for free/delegated inference.

```bash
python -m agentpipe.server
```

Point your tool to `http://localhost:8000/v1/chat/completions` and use
model names like `kilo/kilo-auto/free`, `opencode/big-pickle`, or
`claude/sonnet`. The model prefix selects which provider to use.

### Via curl (OpenAI format)

```bash
curl http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write tests"}]}'
```

### Via native API (persistent sessions)

```bash
# Create an agent
curl -X POST http://localhost:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{"name":"tester","provider":"kilo"}'

# Delegate a task
curl -X POST http://localhost:8000/agents/tester/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Write tests for src/utils.py"}'
```

Sessions persist across requests automatically. Use the `user` field in
OpenAI requests to control session identity.

Docker: `docker compose up`
