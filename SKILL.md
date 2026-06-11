# agentpipe — delegate work to cheaper agents

You are an expensive coding agent. agentpipe lets you offload grunt work to
free or cheap local agents from a single shell call, so your own tokens go to
the parts that actually need you. The delegated agent runs on this machine
with its own CLI and auth; you just call `agentpipe` and read stdout.

## Quick reference

```bash
agentpipe run -p opencode-free "Write pytest tests for src/parser.py"
agentpipe run "One-off question"                 # no -p: cascades over free models
agentpipe run -p gemini-flash -f notes.md        # prompt from a file
echo "$LONG_PROMPT" | agentpipe run -p kilo      # prompt from stdin
agentpipe run -p claude --json "task"            # JSON: text + model + token usage
agentpipe cascade --profile coding "Refactor utils.py to use async IO"
agentpipe batch prompts.jsonl -o results.jsonl   # dataset creation (see below)
agentpipe providers                              # which provider CLIs are installed
agentpipe tiers                                  # known models grouped by cost tier
```

`run` exits 0 with the answer on stdout, non-zero with the error on stderr.
Set a working directory with `--cwd` when the task should see a repo.

## Choosing a worker

| Task | Delegate to | Cost |
|------|-------------|------|
| Boilerplate, tests, docstrings | `opencode-free` or `kilo` | $0 |
| Drafting docs / README | `gemini-flash` | free tier |
| Bulk text generation, datasets | `agentpipe batch` (cascade) | $0 by default |
| Code review second opinion | `claude-sonnet` or `gemini-pro` | paid — use sparingly |
| Anything where free models flake | `agentpipe cascade` | falls back automatically |

Without `-p`, `run` and `batch` use the model cascade: free models first,
automatic fallback on rate limits and errors. That is the right default for
fire-and-forget delegation.

## Dataset creation with `batch`

Input is JSONL (`{"id": ..., "prompt": ...}` per line) or plain text (one
prompt per line, or `-` for stdin). Output is one JSON object per item:

```json
{"index": 0, "id": "q1", "prompt": "...", "text": "...", "error": null,
 "provider": "opencode-free", "model": "opencode/big-pickle",
 "duration_seconds": 4.2, "cost_usd": null, "ok": true}
```

```bash
# 500 prompts, 4 in flight, free cascade, append results as they finish
agentpipe batch prompts.jsonl -o results.jsonl -c 4

# Interrupted or some items failed? Rerun with --resume:
# successful ids are skipped, failed ones are retried.
agentpipe batch prompts.jsonl -o results.jsonl -c 4 --resume

# Pin one provider, custom field names
agentpipe batch qa.jsonl -o out.jsonl -p kilo --prompt-field question --id-field key
```

Failed items are recorded (`"ok": false`, error message in `error`) instead of
aborting the run; the exit code is 1 if any item failed. Filter with
`jq 'select(.ok)'`.

## Python API (multi-step pipelines)

For anything beyond a single shell call — draft/review chains, fan-out with
shared state, validation loops — use the library:

```python
import asyncio
from agentpipe import Agent, cascade, delegate, fan_out, run_batch

async def main():
    # one-shot
    text = await Agent("opencode-free").generate("Write a palindrome checker")

    # cheap drafter + smart reviewer
    final = await delegate(Agent("kilo"), Agent("claude-sonnet"),
                           "Write unit tests for src/db.py", "Review for gaps")

    # parallel prompts on one agent
    reviews = await fan_out(Agent("kilo"), ["Review a.py", "Review b.py"],
                            max_concurrency=3, return_exceptions=True)

    # dataset run with per-item error capture
    items = await run_batch(open("prompts.txt").read().splitlines(),
                            profile="free-only", max_concurrency=4)
    good = [i for i in items if i.ok]

asyncio.run(main())
```

See `docs/` for the full API (sessions, streaming events, cascade profiles,
HTTP server with an OpenAI-compatible endpoint).

## When NOT to delegate

- Architecture decisions, security-sensitive changes, tricky debugging —
  free models get these wrong and you will spend more tokens fixing the mess.
- Tasks needing context only you have (long conversation history); the
  delegate only sees the prompt you send and the `--cwd` you give it.
- Anything under ~10 lines of trivial output — the subprocess round-trip
  costs more than just writing it.

## Wiring this skill into an agent

Point the agent's instruction file at this document — `CLAUDE.md` (Claude
Code), `AGENTS.md` (OpenCode), `GEMINI.md` (Gemini CLI), `.cursorrules`
(Cursor), `.github/copilot-instructions.md` (Copilot) — with one line:

```markdown
Delegate grunt work to cheaper agents with the `agentpipe` CLI; see SKILL.md.
```

Requires `pip install agentpipe` plus at least one provider CLI installed and
authenticated (run `agentpipe providers` to check).
