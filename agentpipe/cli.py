"""agentpipe command-line interface.

One-shot delegation without writing a Python script — the entry point coding
agents (Claude Code, OpenCode, Gemini CLI, ...) use to offload work to
cheaper agents from a single shell call.

    agentpipe run -p opencode-free "Write pytest tests for src/parser.py"
    agentpipe run "Quick question"                  # no provider -> free cascade
    agentpipe cascade --profile coding "Refactor"   # explicit cascade controls
    agentpipe batch prompts.jsonl -o out.jsonl      # dataset creation
    agentpipe providers                             # what is installed
    agentpipe tiers                                 # models by cost tier
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys

from ._agent import _PROVIDER_MAP, DEFAULT_MODELS, Agent
from .batch import iter_batch
from .cascade import CASCADE_PROFILES, cascade, tier_summary

DEFAULT_PROVIDER_ENV = "AGENTPIPE_PROVIDER"


def _read_prompt(args: argparse.Namespace) -> str:
    if args.file:
        if args.file == "-":
            return sys.stdin.read()
        with open(args.file, encoding="utf-8") as f:
            return f.read()
    if args.prompt == "-" or (args.prompt is None and not sys.stdin.isatty()):
        return sys.stdin.read()
    if args.prompt is None:
        raise SystemExit("error: no prompt given (positional argument, --file, or stdin)")
    return args.prompt


def _cmd_run(args: argparse.Namespace) -> int:
    prompt = _read_prompt(args).strip()
    if not prompt:
        print("error: empty prompt", file=sys.stderr)
        return 2

    provider = args.provider or os.environ.get(DEFAULT_PROVIDER_ENV)

    if provider:
        agent = Agent(provider, model=args.model, cwd=args.cwd, timeout=args.timeout)
        try:
            result = asyncio.run(agent.generate_full(prompt))
        except Exception as e:
            print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        if args.json:
            usage = result.usage
            print(
                json.dumps(
                    {
                        "text": result.text,
                        "provider": provider,
                        "model": agent.model,
                        "session_id": result.session_id,
                        "cost_usd": usage.cost_usd if usage else None,
                        "input_tokens": usage.input_tokens if usage else 0,
                        "output_tokens": usage.output_tokens if usage else 0,
                    }
                )
            )
        else:
            print(result.text)
        return 0

    # No provider given: fall back to the model cascade (free models first).
    try:
        cascade_result = asyncio.run(
            cascade(prompt, profile=args.profile, per_attempt_timeout=args.timeout, cwd=args.cwd)
        )
    except Exception as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(
            json.dumps(
                {
                    "text": cascade_result.text,
                    "provider": cascade_result.successful_provider,
                    "model": cascade_result.successful_model,
                    "attempts": cascade_result.attempt_count,
                    "cost_usd": cascade_result.total_cost_usd,
                }
            )
        )
    else:
        print(cascade_result.text)
    return 0


def _load_batch_prompts(path: str, *, prompt_field: str, id_field: str) -> list[tuple[str, str]]:
    """Load prompts from a JSONL file, a plain-text file (one per line), or stdin."""
    if path == "-":
        raw = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as f:
            raw = f.read()

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        raise SystemExit("error: no prompts in input")

    pairs: list[tuple[str, str]] = []
    if lines[0].startswith("{"):
        for idx, line in enumerate(lines):
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise SystemExit(f"error: bad JSON on input line {idx + 1}: {e}") from None
            prompt = row.get(prompt_field)
            if not prompt:
                raise SystemExit(f"error: input line {idx + 1} has no '{prompt_field}' field")
            pairs.append((str(row.get(id_field, idx)), prompt))
    else:
        pairs = [(str(idx), line) for idx, line in enumerate(lines)]
    return pairs


def _completed_ids(output_path: str) -> set[str]:
    """Ids already answered successfully in an existing output file."""
    done: set[str] = set()
    try:
        with open(output_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("error") is None and "id" in row:
                    done.add(str(row["id"]))
    except FileNotFoundError:
        pass
    return done


def _cmd_batch(args: argparse.Namespace) -> int:
    pairs = _load_batch_prompts(args.input, prompt_field=args.prompt_field, id_field=args.id_field)

    skip_ids: set[str] = set()
    if args.resume:
        if not args.output:
            print("error: --resume requires --output", file=sys.stderr)
            return 2
        skip_ids = _completed_ids(args.output)
        if skip_ids:
            print(f"resuming: {len(skip_ids)}/{len(pairs)} already done", file=sys.stderr)

    agent = None
    if args.provider:
        agent = Agent(args.provider, model=args.model, cwd=args.cwd, timeout=args.timeout)

    ok_count = 0
    fail_count = 0
    total_cost = 0.0

    async def _run(out) -> None:
        nonlocal ok_count, fail_count, total_cost
        async for item in iter_batch(
            pairs,
            agent=agent,
            profile=args.profile,
            max_concurrency=args.concurrency,
            timeout=args.timeout,
            cwd=args.cwd,
            max_retries=args.retries,
            skip_ids=skip_ids,
        ):
            out.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")
            out.flush()
            if item.ok:
                ok_count += 1
                if item.cost_usd:
                    total_cost += item.cost_usd
            else:
                fail_count += 1
            done = ok_count + fail_count
            print(
                f"[{done}/{len(pairs) - len(skip_ids)}] {item.id}: {'ok' if item.ok else item.error}",
                file=sys.stderr,
            )

    if args.output:
        with open(args.output, "a", encoding="utf-8") as out:
            asyncio.run(_run(out))
    else:
        asyncio.run(_run(sys.stdout))

    print(f"batch done: {ok_count} ok, {fail_count} failed, ${total_cost:.4f}", file=sys.stderr)
    return 0 if fail_count == 0 else 1


def _cmd_providers(args: argparse.Namespace) -> int:
    rows = []
    for key in sorted(_PROVIDER_MAP):
        try:
            binary = _PROVIDER_MAP[key]().binary_name
        except Exception:
            binary = "?"
        path = shutil.which(binary) if binary != "?" else None
        rows.append(
            {
                "provider": key,
                "binary": binary,
                "installed": path is not None,
                "path": path,
                "default_model": DEFAULT_MODELS.get(key),
            }
        )
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        width = max(len(r["provider"]) for r in rows)
        for r in rows:
            mark = "x" if r["installed"] else " "
            print(f"[{mark}] {r['provider']:<{width}}  {r['binary']:<10}  {r['default_model'] or ''}")
        print("\n[x] = CLI binary found in PATH (auth not checked)")
    return 0


def _cmd_tiers(args: argparse.Namespace) -> int:
    summary = tier_summary()
    if args.json:
        print(
            json.dumps(
                {tier.name.lower(): [m["model"] for m in models] for tier, models in summary.items()},
                indent=2,
            )
        )
    else:
        for tier, models in summary.items():
            print(f"{tier.name}:")
            for m in models:
                print(f"  {m['model']}  ({m['provider']})")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentpipe",
        description="Delegate prompts to local coding-agent CLIs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Send one prompt to an agent (or the free cascade)")
    run.add_argument("prompt", nargs="?", help="The prompt ('-' or omit to read stdin)")
    run.add_argument("-p", "--provider", help=f"Provider key (default: ${DEFAULT_PROVIDER_ENV}, else cascade)")
    run.add_argument("-m", "--model", help="Model override for the provider")
    run.add_argument("-f", "--file", help="Read the prompt from a file ('-' for stdin)")
    run.add_argument(
        "--profile", default="default", choices=list(CASCADE_PROFILES), help="Cascade profile when no provider is given"
    )
    run.add_argument("--cwd", default="/tmp", help="Working directory for the agent (default: /tmp)")
    run.add_argument("--timeout", type=int, default=300, help="Timeout in seconds (default: 300)")
    run.add_argument("--json", action="store_true", help="Emit JSON with text, model, and usage")
    run.set_defaults(func=_cmd_run)

    # Listed for discoverability; execution is intercepted in main() and
    # handed to cascade_run, which owns the full flag set.
    sub.add_parser("cascade", help="Try models in priority order with automatic fallback", add_help=False)

    batch = sub.add_parser("batch", help="Run many prompts; JSONL in, JSONL out (dataset creation)")
    batch.add_argument("input", help="Prompts file: .jsonl, plain text (one per line), or '-' for stdin")
    batch.add_argument("-o", "--output", help="Output JSONL (appended; default: stdout)")
    batch.add_argument("-p", "--provider", help="Provider key (default: cascade per prompt)")
    batch.add_argument("-m", "--model", help="Model override for the provider")
    batch.add_argument(
        "--profile", default="default", choices=list(CASCADE_PROFILES), help="Cascade profile when no provider is given"
    )
    batch.add_argument("-c", "--concurrency", type=int, default=4, help="Prompts in flight at once (default: 4)")
    batch.add_argument("--retries", type=int, default=0, help="Extra attempts per failed prompt (default: 0)")
    batch.add_argument("--resume", action="store_true", help="Skip ids already answered in --output")
    batch.add_argument("--prompt-field", default="prompt", help="JSONL field holding the prompt (default: prompt)")
    batch.add_argument("--id-field", default="id", help="JSONL field holding the item id (default: id)")
    batch.add_argument("--cwd", default="/tmp", help="Working directory for the agents (default: /tmp)")
    batch.add_argument("--timeout", type=int, default=300, help="Per-prompt timeout in seconds (default: 300)")
    batch.set_defaults(func=_cmd_batch)

    providers = sub.add_parser("providers", help="List provider keys and which CLIs are installed")
    providers.add_argument("--json", action="store_true")
    providers.set_defaults(func=_cmd_providers)

    tiers = sub.add_parser("tiers", help="List known models grouped by cost tier")
    tiers.add_argument("--json", action="store_true")
    tiers.set_defaults(func=_cmd_tiers)

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "cascade":
        from .cascade_run import main as cascade_main

        cascade_main(argv[1:])
        return 0
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
