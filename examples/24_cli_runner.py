"""
CLI cascade runner — demonstrates the command-line interface.

Usage:
    python -m agentpipe.cascade_run "Explain Python decorators"
    python -m agentpipe.cascade_run --profile coding "Write tests"
    python -m agentpipe.cascade_run --free-only "Quick question"
    python -m agentpipe.cascade_run --max-tier cheap "Refactor"
    python -m agentpipe.cascade_run --models "opencode/big-pickle,gemini-2.5-flash" "Summarize"
    python -m agentpipe.cascade_run --profile coding --max-attempts 3 --timeout 60 "Prompt"
    python -m agentpipe.cascade_run --json "Explain this architecture"

For more details, see docs/cascade.md
"""

# This is a usage reference only — the actual runner is at agentpipe.cascade_run
# To run:
#   python -m agentpipe.cascade_run "Your prompt here"
