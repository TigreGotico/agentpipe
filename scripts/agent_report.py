#!/usr/bin/env python3
"""Agent subscriptions and usage report — rerun anytime for a bird's-eye view."""

import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def run(cmd: list[str], timeout: int = 15) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def run_json(cmd: list[str], timeout: int = 15) -> dict | None:
    out = run(cmd, timeout)
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def subsection(title: str) -> None:
    print(f"--- {title} ---\n")


def check_binary(name: str) -> str | None:
    return shutil.which(name)


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n/1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def fmt_dollars(n: float) -> str:
    if n >= 1000:
        return f"${n:,.0f}"
    if n >= 1:
        return f"${n:.2f}"
    return f"${n:.4f}"


def collect_claude_usage() -> dict:
    total_input = 0
    total_output = 0
    total_cache_read = 0
    total_cache_write = 0
    msg_count = 0
    model_usage = defaultdict(lambda: {"input": 0, "output": 0, "count": 0})

    proj_dir = Path.home() / ".claude" / "projects"
    if not proj_dir.exists():
        return {}

    for jsonl in proj_dir.rglob("*.jsonl"):
        try:
            with open(jsonl) as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        msg = d.get("message", {})
                        if isinstance(msg, dict) and "usage" in msg:
                            u = msg["usage"]
                            inp = u.get("input_tokens", 0)
                            out = u.get("output_tokens", 0)
                            cr = u.get("cache_read_input_tokens", 0)
                            cw = u.get("cache_creation_input_tokens", 0)
                            total_input += inp
                            total_output += out
                            total_cache_read += cr
                            total_cache_write += cw
                            msg_count += 1
                            model = msg.get("model", "unknown")
                            model_usage[model]["input"] += inp
                            model_usage[model]["output"] += out
                            model_usage[model]["count"] += 1
                    except (json.JSONDecodeError, KeyError):
                        pass
        except OSError:
            pass

    inp_cost = total_input * 3 / 1_000_000
    out_cost = total_output * 15 / 1_000_000
    cr_cost = total_cache_read * 0.30 / 1_000_000
    cw_cost = total_cache_write * 3.75 / 1_000_000
    total_cost = inp_cost + out_cost + cr_cost + cw_cost

    return {
        "messages": msg_count,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cache_read_tokens": total_cache_read,
        "cache_write_tokens": total_cache_write,
        "est_input_cost": inp_cost,
        "est_output_cost": out_cost,
        "est_cache_read_cost": cr_cost,
        "est_cache_write_cost": cw_cost,
        "est_total_cost": total_cost,
        "models": dict(model_usage),
    }


def collect_opencode_usage() -> dict:
    stats_raw = run(["opencode", "stats"])
    if not stats_raw:
        return {}
    parsed = {}
    for line in stats_raw.split("\n"):
        line = line.strip()
        if "│" in line:
            parts = [p.strip() for p in line.split("│") if p.strip()]
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                parsed[key] = val
    return parsed


def collect_vibe_usage() -> dict:
    logs_dir = Path.home() / ".vibe" / "logs" / "session"
    total_cost = 0.0
    total_tokens = 0
    total_input = 0
    total_output = 0
    sessions = 0

    for session_dir in logs_dir.iterdir():
        meta = session_dir / "meta.json"
        if not meta.exists():
            continue
        try:
            d = json.loads(meta.read_text())
            stats = d.get("stats", {})
            total_cost += stats.get("session_cost", 0)
            total_tokens += stats.get("session_total_llm_tokens", 0)
            total_input += stats.get("session_prompt_tokens", 0)
            total_output += stats.get("session_completion_tokens", 0)
            sessions += 1
        except (json.JSONDecodeError, KeyError):
            pass

    return {
        "sessions": sessions,
        "total_cost": total_cost,
        "total_tokens": total_tokens,
        "total_input": total_input,
        "total_output": total_output,
    }


# ──────────────────────────────────────────────
# 1. BINARY PRESENCE
# ──────────────────────────────────────────────
section("1. INSTALLED BINARIES")

AGENTS = ["claude", "gemini", "opencode", "vibe"]
for name in AGENTS:
    path = check_binary(name)
    status = path or "NOT FOUND"
    ver_cmd = {"claude": ["claude", "--version"],
               "gemini": ["gemini", "--version"],
               "opencode": ["opencode", "--version"],
               "vibe": ["vibe", "--version"]}.get(name)
    ver = run(ver_cmd, timeout=5) if path else None
    line = f"  {name:12s} {status}"
    if ver:
        line += f"  ({ver.split(chr(10))[0]})"
    print(line)


# ──────────────────────────────────────────────
# 2. CLAUDE
# ──────────────────────────────────────────────
section("2. CLAUDE CODE")

claude_auth = run_json(["claude", "auth", "status", "--json"])
if claude_auth:
    print(f"  Email:          {claude_auth.get('email', 'N/A')}")
    print(f"  Authenticated:  {claude_auth.get('loggedIn', False)}")
    print(f"  Method:         {claude_auth.get('authMethod', 'N/A')}")
    print(f"  Subscription:   {claude_auth.get('subscriptionType', 'N/A')}")
    print(f"  API Provider:   {claude_auth.get('apiProvider', 'N/A')}")
    if claude_auth.get("orgName"):
        print(f"  Org:            {claude_auth['orgName']}")
    tier = claude_auth.get("rateLimitTier", "")
    if tier:
        print(f"  Rate Tier:      {tier}")
else:
    print("  NOT AUTHENTICATED (or claude not installed)")

print()
subsection("Claude Plans")
print("  Free:     5 messages/8hr — no subscription needed")
print("  Pro:      45 messages/5hr — $20/mo")
print("  Max 5x:   225 messages/5hr — $100/mo")
print("  Max 20x:  900 messages/5hr — $200/mo")
if claude_auth:
    sub = claude_auth.get("subscriptionType", "")
    print(f"\n  >>> Your subscription: {sub}")

print()
subsection("Claude Token Usage (from local session logs)")
claude_usage = collect_claude_usage()
if claude_usage:
    print(f"  Total messages:          {claude_usage['messages']:,}")
    print(f"  Input tokens:            {fmt_tokens(claude_usage['input_tokens'])}")
    print(f"  Output tokens:           {fmt_tokens(claude_usage['output_tokens'])}")
    print(f"  Cache read tokens:       {fmt_tokens(claude_usage['cache_read_tokens'])}")
    print(f"  Cache write tokens:      {fmt_tokens(claude_usage['cache_write_tokens'])}")
    print()
    print(f"  Est. cost at API rates:  {fmt_dollars(claude_usage['est_total_cost'])}")
    print(f"    Input:                 {fmt_dollars(claude_usage['est_input_cost'])}")
    print(f"    Output:                {fmt_dollars(claude_usage['est_output_cost'])}")
    print(f"    Cache read:            {fmt_dollars(claude_usage['est_cache_read_cost'])}")
    print(f"    Cache write:           {fmt_dollars(claude_usage['est_cache_write_cost'])}")
    print()
    print(f"  >>> Effective cost covered by Max subscription: {fmt_dollars(claude_usage['est_total_cost'])}")
    print(f"  >>> Monthly budget: $200/mo => {fmt_dollars(claude_usage['est_total_cost'])} used = ~{min(claude_usage['est_total_cost']/200*100, 100):.0f}% of 1 month's sub")
    print()
    print("  Per-model breakdown:")
    for model, u in sorted(claude_usage["models"].items(), key=lambda x: x[1]["count"], reverse=True)[:8]:
        short = model.replace("claude-", "c-").replace("-20251001", "")
        print(f"    {short:30s} {u['count']:>6,} msgs  {fmt_tokens(u['input']):>8s} in  {fmt_tokens(u['output']):>8s} out")
else:
    print("  No session data found")


# ──────────────────────────────────────────────
# 3. GEMINI
# ──────────────────────────────────────────────
section("3. GEMINI CLI")

gemini_ver = run(["gemini", "--version"])
if gemini_ver:
    print(f"  Version: {gemini_ver.split(chr(10))[0]}")

gemini_accounts = Path.home() / ".gemini" / "google_accounts.json"
if gemini_accounts.exists():
    try:
        accts = json.loads(gemini_accounts.read_text())
        if isinstance(accts, dict):
            active = accts.get("active", "N/A")
            print(f"  Account: {active}")
    except json.JSONDecodeError:
        pass

print()
subsection("Gemini Plans")
print("  Free:     Gemini 2.5 Flash — 15 RPM, 1M tokens/min context")
print("  Free:     Gemini 2.5 Pro  — 5 RPM, limited context")
print("  Paid:     Higher RPM/limits with Google AI Studio billing")
print("  Auth:     Browser OAuth (no API key needed for free tier)")
print()
print("  >>> Free tier: 15 RPM for Flash, 5 RPM for Pro")
print("  >>> No token cap on free tier (rate-limited, not budget-limited)")


# ──────────────────────────────────────────────
# 4. OPENCODE
# ──────────────────────────────────────────────
section("4. OPENCODE (Zen + Go)")

providers_out = run(["opencode", "providers", "list"])
if providers_out:
    print(providers_out)
else:
    print("  Could not read provider status")

print()
subsection("OpenCode Free Models (Zen endpoint, $0)")
FREE_MODELS = [
    "opencode/big-pickle",
    "opencode/gemini-3-flash",
    "opencode/deepseek-v4-flash-free",
    "opencode/mimo-v2.5-free",
    "opencode/nemotron-3-super-free",
    "opencode/minimax-m3-free",
]
for m in FREE_MODELS:
    print(f"  {m}")

print()
subsection("OpenCode Zen Pay-As-You-Go Models (selected)")
ZEN_MODELS = [
    "opencode/claude-sonnet-4-5",
    "opencode/claude-opus-4-8",
    "opencode/kimi-k2.5",
    "opencode/kimi-k2.6",
    "opencode/glm-5.1",
    "opencode/minimax-m2.7",
    "opencode/gpt-5",
    "opencode/qwen3.6-plus",
]
for m in ZEN_MODELS:
    print(f"  {m}")

print()
subsection("OpenCode Go Models (selected)")
GO_MODELS = [
    "opencode-go/deepseek-v4-flash",
    "opencode-go/deepseek-v4-pro",
    "opencode-go/glm-5.1",
    "opencode-go/kimi-k2.6",
    "opencode-go/qwen3.7-max",
]
for m in GO_MODELS:
    print(f"  {m}")

print()
subsection("OpenCode Usage Stats")
oc_stats = collect_opencode_usage()
if oc_stats:
    total_cost = float(oc_stats.get("Total Cost", "$0").replace("$", "").replace(",", ""))
    print(f"  Sessions:           {oc_stats.get('Sessions', 'N/A')}")
    print(f"  Messages:           {oc_stats.get('Messages', 'N/A')}")
    print(f"  Days active:        {oc_stats.get('Days', 'N/A')}")
    print(f"  Total cost:         {oc_stats.get('Total Cost', 'N/A')}")
    print(f"  Avg cost/day:       {oc_stats.get('Avg Cost/Day', 'N/A')}")
    print(f"  Input tokens:       {oc_stats.get('Input', 'N/A')}")
    print(f"  Output tokens:      {oc_stats.get('Output', 'N/A')}")
    print(f"  Cache read:          {oc_stats.get('Cache Read', 'N/A')}")
    print(f"  Cache write:        {oc_stats.get('Cache Write', 'N/A')}")
    print(f"  Avg tokens/session: {oc_stats.get('Avg Tokens/Session', 'N/A')}")
    print(f"  Median tokens/sess: {oc_stats.get('Median Tokens/Session', 'N/A')}")
    print()
    print(f"  >>> Total spent: ~${total_cost:.2f}")
    print(f"  >>> Zen = pay-as-you-go (no fixed budget, costs accrue per token)")
else:
    stats_raw = run(["opencode", "stats"])
    if stats_raw:
        for line in stats_raw.split("\n")[:16]:
            print(f"  {line}")
    else:
        print("  Could not read stats (run `opencode stats` manually)")

print()
subsection("OpenCode Plans")
print("  Free:   $0 — free models only (6 free models)")
print("  Zen:    Pay-as-you-go — full model catalog, per-token billing")
print("  Go:     $5-10/mo subscription — higher rate limits, flat billing")


# ──────────────────────────────────────────────
# 5. MISTRAL VIBE
# ──────────────────────────────────────────────
section("5. MISTRAL VIBE")

vibe_config = Path.home() / ".vibe" / "config.toml"
vibe_env = Path.home() / ".vibe" / ".env"

if vibe_config.exists():
    print("  Config:    ~/.vibe/config.toml ✓")
    try:
        content = vibe_config.read_text()
        for line in content.split("\n"):
            if line.startswith("active_model"):
                print(f"  {line.strip()}")
            if line.startswith("enable_telemetry"):
                print(f"  {line.strip()}")
    except Exception:
        pass
else:
    print("  Config:    not found (run `vibe` to create)")

if vibe_env.exists():
    has_key = "MISTRAL_API_KEY" in vibe_env.read_text()
    print(f"  API Key:   {'set ✓' if has_key else 'NOT SET'}")
else:
    print("  API Key:   NOT SET (run `vibe --setup`)")

vibe_ver = run(["vibe", "--version"], timeout=5)
if vibe_ver:
    print(f"  Version:   {vibe_ver.split(chr(10))[0]}")

print()
subsection("Vibe Usage (from local session logs)")
vibe_usage = collect_vibe_usage()
if vibe_usage and vibe_usage["sessions"] > 0:
    print(f"  Sessions:          {vibe_usage['sessions']}")
    print(f"  Total tokens:      {fmt_tokens(vibe_usage['total_tokens'])}")
    print(f"  Total cost:        {fmt_dollars(vibe_usage['total_cost'])}")
    print(f"  Input tokens:      {fmt_tokens(vibe_usage['total_input'])}")
    print(f"  Output tokens:     {fmt_tokens(vibe_usage['total_output'])}")
    print()
    print("  >>> Vibe uses Mistral API — pay-per-token with Mistral API key")
    print("  >>> devstral-2: $0.40/M input, $2.00/M output")
    print(f"  >>> Your devstral-2 usage so far: {fmt_dollars(vibe_usage['total_cost'])}")
else:
    print("  No session data found (or stats are zeroed)")

print()
subsection("Vibe Plans")
print("  Free:     Mistral API free tier — limited RPM (500K tokens/mo)")
print("  Pay-go:   Per-token billing via Mistral API key")
print("  Note:     Uses MISTRAL_API_KEY from ~/.vibe/.env or env var")
print("  Key models: mistral-large-latest, devstral-2, codestral-latest")


# ──────────────────────────────────────────────
# 6. BUDGET & USAGE SUMMARY
# ──────────────────────────────────────────────
section("6. BUDGET & USAGE SUMMARY")

print("  Provider         Plan          Spent          Budget          %Used")
print("  " + "-"*70)

if claude_auth and claude_usage:
    sub = claude_auth.get("subscriptionType", "")
    if sub == "max":
        budget = 200.0
        spent = claude_usage["est_total_cost"]
        pct = min(spent / budget * 100, 100)
        print(f"  Claude Code      Max 20x       {fmt_dollars(spent):>12s}   $200/mo sub     ~{pct:.0f}%")
        print(f"                                  (covered by sub — no per-token charge)")
    else:
        print(f"  Claude Code      {sub:<13s} {fmt_dollars(claude_usage['est_total_cost']):>12s}   —               —")
else:
    print("  Claude Code      —             —              —               —")

if oc_stats:
    try:
        oc_cost = float(oc_stats.get("Total Cost", "$0").replace("$", "").replace(",", ""))
        print(f"  OpenCode Zen     Pay-go        {fmt_dollars(oc_cost):>12s}   No cap (pay-go)  ∞")
    except ValueError:
        print("  OpenCode Zen     Pay-go        —              No cap (pay-go)  ∞")
else:
    print("  OpenCode Zen     Pay-go        —              No cap (pay-go)  ∞")

print(f"  Gemini CLI       Free           $0.00          Free tier       0%")

if vibe_usage and vibe_usage["sessions"] > 0:
    print(f"  Mistral Vibe     Free/pay-go   {fmt_dollars(vibe_usage['total_cost']):>12s}   500K tok/mo free  ~{min(vibe_usage['total_cost']/1*100, 100):.0f}%*")
else:
    print(f"  Mistral Vibe     Free/pay-go   $0.00          500K tok/mo free  0%")

print()
print("  * Mistral free tier: ~500K tokens/mo, ~1 RPM. Vibe sessions show")
print("    $0 token counts because pricing is applied per-call at Mistral's API.")


# ──────────────────────────────────────────────
# 7. FREE MODEL INVENTORY
# ──────────────────────────────────────────────
section("7. FREE MODEL INVENTORY")

print("  Models with $0 cost across all providers:\n")

free_models = [
    ("opencode/big-pickle", "OpenCode Free/Zen", "General coding, free"),
    ("opencode/gemini-3-flash", "OpenCode Free/Zen", "Fast, free tier"),
    ("opencode/deepseek-v4-flash-free", "OpenCode Free/Zen", "DeepSeek free tier"),
    ("opencode/mimo-v2.5-free", "OpenCode Free/Zen", "MiMo free tier"),
    ("opencode/nemotron-3-super-free", "OpenCode Free/Zen", "Nemotron free tier"),
    ("opencode/minimax-m3-free", "OpenCode Free/Zen", "MiniMax free tier"),
    ("gemini-2.5-flash", "Gemini CLI", "15 RPM free tier"),
    ("mistral-large-latest", "Mistral Vibe", "Free tier with rate limits"),
    ("devstral-2", "Mistral Vibe", "Code model, free tier"),
]

print(f"  {'Model':40s} {'Provider':18s} {'Notes'}")
print(f"  {'-'*40} {'-'*18} {'-'*30}")
for model, provider, notes in free_models:
    print(f"  {model:40s} {provider:18s} {notes}")

print(f"\n  Total: {len(free_models)} free models across {len(set(p for _, p, _ in free_models))} providers")


# ──────────────────────────────────────────────
# 8. USAGE TIPS
# ──────────────────────────────────────────────
section("8. USAGE & RATE LIMIT TIPS")

print("  Claude Max:   ~900 messages/5hr, $200/mo — all token costs covered")
print("  Gemini Free:  15 RPM, 1500 RPD for Flash; 5 RPM for Pro")
print("  OpenCode:     Per-model rate limits on Go; Free models unlimited (Zen)")
print("  Vibe Free:    Mistral free tier ~1 RPM, 500K tokens/mo")
print()
print("  For maximum free compute:")
print("    1. Use OpenCode Free models (6 free models, no API key needed)")
print("    2. Use Gemini Flash (15 RPM free)")
print("    3. Use cascade_free_only() for automatic failover across free models")
print("    4. Use Mistral Vibe for Mistral models on free tier")