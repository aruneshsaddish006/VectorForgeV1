# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Vector-Forge conversational API (LangGraph + FastAPI)
# Entrypoint: conversational.main:app   Port: 8001
# Build for EC2 (linux/amd64) from Apple M4:
#   docker buildx build --platform linux/amd64 --load -t vectorforge-conversational:latest .
# ---------------------------------------------------------------------------

FROM python:3.11-slim

# Install uv
RUN pip install --no-cache-dir uv

# /workspace/conversational is the package root.
# PYTHONPATH=/workspace lets Python resolve "import conversational".
WORKDIR /workspace/conversational

# Non-root user
RUN groupadd --system --gid 1001 appuser \
 && useradd  --system --uid 1001 --gid appuser appuser

# Copy dependency files first — cached unless lock/manifest changes
COPY pyproject.toml uv.lock ./

# Install production dependencies into an isolated venv
RUN uv sync --no-dev --frozen

# Copy application source + bundled .env
COPY . .

ENV PYTHONPATH=/workspace \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN chown -R appuser:appuser /workspace
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/health').status==200 else 1)"

CMD ["uv", "run", "uvicorn", "conversational.main:app", "--host", "0.0.0.0", "--port", "8001"]
