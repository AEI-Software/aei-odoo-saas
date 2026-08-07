# Tenant AI agent — FastAPI wrapper around the Claude Agent SDK.
# The claude-agent-sdk pip package bundles its own standalone `claude` CLI
# binary (claude_agent_sdk/_bundled/claude) — no separate Node.js runtime
# needed in this image.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Runs as non-root, same convention as portal/Dockerfile
RUN adduser --disabled-password --gecos "" agent \
    && mkdir -p /data \
    && chown -R agent /app /data
USER agent

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
