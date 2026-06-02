FROM python:3.11-slim

WORKDIR /app

# Install build deps, then copy and install from source
COPY pyproject.toml README.md ./
COPY agentpipe/ agentpipe/
RUN pip install --no-cache-dir . fastapi uvicorn[standard] sse-starlette

EXPOSE 8000

CMD ["uvicorn", "agentpipe.server:app", "--host", "0.0.0.0", "--port", "8000"]
