"""
HTTP Server — run multiple agents behind HTTP with persistent sessions.

Usage:
    pip install agentpipe fastapi uvicorn sse-starlette
    python -m agentpipe.server

Then:
    # OpenAI-compatible — use with any OpenAI SDK/client
    curl http://localhost:8000/v1/chat/completions \
      -H 'Content-Type: application/json' \
      -d '{"model":"kilo/kilo-auto/free","messages":[{"role":"user","content":"Write tests"}]}'

    # Native API — create and call named agents
    curl -X POST http://localhost:8000/agents \
      -H 'Content-Type: application/json' \
      -d '{"name":"writer","provider":"kilo"}'
    curl -X POST http://localhost:8000/agents/writer/generate \
      -H 'Content-Type: application/json' \
      -d '{"prompt":"Write unit tests"}'

See agentpipe/server.py for the full implementation.
"""

# This is a usage reference — the server runs as:
#   python -m agentpipe.server
# Or via Docker:
#   docker compose up
