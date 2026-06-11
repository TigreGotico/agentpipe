# Command-Line Interface

The `agentpipe` command turns any installed provider CLI into a one-shot,
scriptable text generator. It is the easiest way for another program — or
another coding agent — to delegate work without writing Python.

```bash
pip install agentpipe
agentpipe --help
```

`python -m agentpipe` is equivalent to `agentpipe`.

## `agentpipe run` — one prompt, one answer

```bash
agentpipe run -p opencode-free "Write pytest tests for src/parser.py"
agentpipe run -p claude -m haiku "Summarize CHANGELOG.md" --cwd .
agentpipe run -f prompt.txt -p gemini-flash      # prompt from a file
echo "long prompt" | agentpipe run -p kilo       # prompt from stdin
agentpipe run -p claude --json "task"            # structured output
```

| Flag | Meaning |
|------|---------|
| `prompt` | Positional prompt; `-` or omitted reads stdin |
| `-p, --provider` | Provider key (`agentpipe providers` lists them). Defaults to `$AGENTPIPE_PROVIDER`; if unset, the prompt goes through the model cascade |
| `-m, --model` | Model override for the provider |
| `-f, --file` | Read the prompt from a file (`-` for stdin) |
| `--profile` | Cascade profile used when no provider is given (default: `default`) |
| `--cwd` | Working directory the agent runs in (default: `/tmp`) |
| `--timeout` | Seconds before the agent process is killed (default: 300) |
| `--json` | Emit `{"text", "provider", "model", "session_id", "cost_usd", "input_tokens", "output_tokens"}` |

Exit code 0 on success (answer on stdout), 1 on failure (error on stderr),
2 on bad input.

Without `-p`, the prompt runs through the [model cascade](cascade.md): free
models first, automatic fallback on rate limits and errors.

## `agentpipe batch` — many prompts, JSONL out

Built for dataset creation: bounded concurrency, incremental writes, per-item
error capture, and resumable runs.

```bash
agentpipe batch prompts.jsonl -o results.jsonl -c 4
agentpipe batch prompts.txt -o out.jsonl -p kilo --retries 1
agentpipe batch prompts.jsonl -o out.jsonl --resume      # continue a run
cat prompts.txt | agentpipe batch - > results.jsonl      # streams to stdout
```

Input formats:

- **JSONL** — one object per line; the prompt is read from `--prompt-field`
  (default `prompt`) and the item id from `--id-field` (default `id`, falls
  back to the line number).
- **Plain text** — one prompt per line; ids are line numbers.
- `-` — read either format from stdin.

Each completed item is appended to `--output` (or stdout) as soon as it
finishes:

```json
{"index": 0, "id": "q1", "prompt": "...", "text": "...", "error": null,
 "provider": "opencode-free", "model": "opencode/big-pickle",
 "duration_seconds": 4.2, "cost_usd": null, "input_tokens": 0,
 "output_tokens": 0, "ok": true}
```

A failed item gets `"ok": false` and the error message in `error` — the run
keeps going. Exit code is 1 if any item failed, 0 otherwise.

`--resume` re-reads the output file and skips ids that already have a
successful answer, so rerunning the same command continues an interrupted run
and retries failures. Progress goes to stderr.

| Flag | Meaning |
|------|---------|
| `-o, --output` | Output JSONL, opened in append mode (default: stdout) |
| `-p, --provider` / `-m, --model` | Pin one provider; omit to cascade per prompt |
| `--profile` | Cascade profile when no provider is given |
| `-c, --concurrency` | Prompts in flight at once (default: 4) |
| `--retries` | Extra attempts per failed prompt (default: 0) |
| `--resume` | Skip ids already answered in `--output` |
| `--prompt-field` / `--id-field` | JSONL field names |
| `--cwd` / `--timeout` | As in `run` (timeout is per prompt) |

The programmatic equivalents are `agentpipe.run_batch` / `agentpipe.iter_batch`
(see [Pipelines](pipelines.md)).

## `agentpipe cascade` — explicit fallback controls

The full cascade front-end (profiles, model lists, tier caps, cost caps).
Identical to `python -m agentpipe.cascade_run`:

```bash
agentpipe cascade "Explain this error"
agentpipe cascade --profile coding --max-tier cheap "Refactor module"
agentpipe cascade --models "opencode/big-pickle,gemini-2.5-flash" --json "Summarize"
```

See [Model Cascade](cascade.md) for profiles and tiers.

## `agentpipe providers` / `agentpipe tiers`

```bash
agentpipe providers          # provider keys, binaries, install status, default models
agentpipe providers --json
agentpipe tiers              # known models grouped FREE → PREMIUM
agentpipe tiers --json
```

`providers` only checks that the binary exists in `PATH`; it does not verify
auth (use the Python `Agent.auth_status()` for that).
