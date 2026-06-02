FROM python:3.12-slim

# Install Node.js for npm-based CLIs (kilo, gemini, qoder)
RUN apt-get update -qq && apt-get install -y -qq curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y -qq nodejs git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install npm-based provider CLIs
RUN npm install -g @kilocode/cli @google/gemini-cli @qoder-ai/qodercli

# Install opencode (Go binary from GitHub releases)
RUN curl -fsSL https://github.com/anomalyco/opencode/releases/latest/download/opencode-linux-x64.tar.gz \
    | tar xz -C /usr/local/bin opencode

# Install pip-based provider CLIs (aider-chat supports python 3.10-3.12)
RUN pip install --quiet aider-chat
# mistral-vibe requires python >=3.12
RUN pip install --quiet mistral-vibe

# Install agentpipe from local source
WORKDIR /app
COPY pyproject.toml README.md SKILL.md LICENSE ./
COPY agentpipe/ agentpipe/
RUN pip install --no-cache-dir . fastapi uvicorn[standard] sse-starlette

# Entrypoint — checks auth, starts server
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "agentpipe.server:app", "--host", "0.0.0.0", "--port", "8000"]
