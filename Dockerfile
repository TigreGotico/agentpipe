FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir agentpipe fastapi uvicorn[standard] sse-starlette

EXPOSE 8000

CMD ["uvicorn", "agentpipe.server:app", "--host", "0.0.0.0", "--port", "8000"]
