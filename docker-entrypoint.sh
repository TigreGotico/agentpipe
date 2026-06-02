#!/bin/bash
set -e

echo "=== agentpipe server ==="
echo ""

# Check each provider CLI
check_cli() {
    if command -v "$1" &>/dev/null; then
        echo "  [OK]   $1 ($($1 --version 2>/dev/null | head -1))"
        return 0
    else
        echo "  [MISS] $1"
        return 1
    fi
}

echo "Provider CLIs:"
check_cli kilo
check_cli opencode
check_cli claude
check_cli gemini
check_cli aider
check_cli vibe
echo ""

# Check auth status
echo "Auth:"
if [ -n "$OPENROUTER_API_KEY" ]; then
    echo "  [OK]   OPENROUTER_API_KEY (shared by aider, kilo, opencode)"
else
    echo "  [WARN] OPENROUTER_API_KEY not set — free models on kilo/opencode may not work"
fi
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "  [OK]   ANTHROPIC_API_KEY (Claude)"
else
    echo "  [WARN] ANTHROPIC_API_KEY not set — Claude requires it"
fi
if [ -n "$MISTRAL_API_KEY" ]; then
    echo "  [OK]   MISTRAL_API_KEY (Vibe)"
fi
echo ""

# Check mounted auth dirs
echo "Auth volumes:"
for d in "$@"; do
    if [ -d "$d" ]; then
        echo "  [OK]   $d"
    fi
done
echo ""

echo "Starting server..."
exec "$@"
