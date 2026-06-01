"""
Provider internals — inspect how commands are built and events are parsed.

Usage:
    python -m examples.22_provider_internals
"""

from agentpipe import (
    ApprovalMode,
    ClaudeProvider,
    GeminiProvider,
    HttpMcpServer,
    OpencodeFreeProvider,
    OpencodeGoProvider,
    OpencodeZenProvider,
    StdioMcpServer,
)


def show_provider(provider, prompt="Summarize this code", **kwargs):
    cmd = provider.build_command(prompt, **kwargs)
    print(f"  {' '.join(cmd)}")


def main():
    print("=== Claude Providers ===\n")

    show_provider(ClaudeProvider())
    show_provider(ClaudeProvider(model="haiku"))
    show_provider(ClaudeProvider(model="opus", approval_mode=ApprovalMode.PLAN))
    show_provider(ClaudeProvider(model="sonnet", approval_mode=ApprovalMode.YOLO))
    show_provider(
        ClaudeProvider(
            model="sonnet",
            mcp_servers=[
                HttpMcpServer(name="docs", url="http://localhost:9000/sse"),
                StdioMcpServer(name="github", command="npx", args=["-y", "@mcp/server-github"]),
            ],
        )
    )
    show_provider(ClaudeProvider(model="sonnet", max_budget_usd=2.50))

    print("\n=== Claude with session resume ===\n")
    show_provider(ClaudeProvider(), session_id="sess-abc123")

    print("\n=== Gemini Providers ===\n")

    show_provider(GeminiProvider())
    show_provider(GeminiProvider(model="gemini-2.5-pro"))

    print("\n=== Gemini with session resume ===\n")
    show_provider(GeminiProvider(), session_id="sess-xyz789")

    print("\n=== OpenCode Providers ===\n")

    for cls, name in [
        (OpencodeFreeProvider, "Free"),
        (OpencodeZenProvider, "Zen"),
        (OpencodeGoProvider, "Go"),
    ]:
        p = cls()
        print(f"--- {name} (plan={p.plan}, model={p.model}) ---")
        show_provider(p)

    print("\n=== OpenCode with session resume ===\n")
    show_provider(OpencodeZenProvider(), session_id="sess-opencode-456")

    print("\n=== Environment Variables ===\n")
    for name, cls in [
        ("Claude", ClaudeProvider),
        ("Gemini", GeminiProvider),
        ("OpenCode", OpencodeZenProvider),
    ]:
        env = cls().build_env()
        interesting = {k: v for k, v in env.items() if k.startswith(("CLAUDE", "GEMINI"))}
        print(f"  {name}: {interesting or '(no special env)'}")


if __name__ == "__main__":
    main()
