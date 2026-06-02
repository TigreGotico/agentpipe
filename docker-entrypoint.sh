#!/bin/bash
set -e

echo "=== agentpipe server ==="
echo ""

check_cli() {
    if command -v "$1" &>/dev/null; then
        local ver=$($1 --version 2>/dev/null | head -1)
        echo "  [OK]   $1 (${ver:-installed})"
    else
        echo "  [MISS] $1"
    fi
}

echo "Provider CLIs:"
check_cli kilo
check_cli opencode
check_cli claude
check_cli gemini
check_cli aider
check_cli vibe
check_cli qodercli
echo ""

echo "Auth:"
if [ -n "$OPENROUTER_API_KEY" ]; then
    echo "  [OK]   OPENROUTER_API_KEY (shared by aider, kilo, opencode)"
else
    echo "  [INFO] OPENROUTER_API_KEY not set — kilo/opencode use free-tier models without it"
fi
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  [OK]   ANTHROPIC_API_KEY (Claude)"
fi
if [ -n "$OPENAI_API_KEY" ]; then
    echo "  [OK]   OPENAI_API_KEY (Qoder, Aider)"
fi
if [ -n "$MISTRAL_API_KEY" ]; then
    echo "  [OK]   MISTRAL_API_KEY (Vibe)"
fi
echo ""

echo "Auth volumes:"
for d in /root/.local/share/kilo /root/.config/opencode /root/.claude /root/.config/gemini /root/.vibe; do
    if [ -d "$d" ]; then
        echo "  [OK]   $d"
    fi
done
echo ""

echo "Starting server..."
exec "$@"
