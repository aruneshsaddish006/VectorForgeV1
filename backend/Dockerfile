# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Vector-Forge backend — main API (FastAPI)
#
# Entrypoint: app:app  (app/main.py -> create_app()).
# Talks to Postgres (RDS) via psycopg and Redis. Listens on :8000, /health.
#
# Reproducible install via uv + the committed uv.lock. Multi-stage so build
# tools don't ship in the runtime image; runs as a non-root user.
# ---------------------------------------------------------------------------

ARG PYTHON_VERSION=3.12-slim

# ---- 1. builder: resolve & install deps into a venv -----------------------
FROM python:${PYTHON_VERSION} AS builder

# uv: fast, lockfile-driven installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# psycopg[binary] ships wheels, so no libpq build deps are needed here.
# Install dependencies first (cached unless lock/manifest changes).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy source and finish the install
COPY . .
RUN uv sync --frozen --no-dev

# ---- 2. runtime: minimal image -------------------------------------------
FROM python:${PYTHON_VERSION} AS runtime

WORKDIR /app

# Non-root user
RUN groupadd --system --gid 1001 appuser \
 && useradd  --system --uid 1001 --gid appuser appuser

# Bring over the resolved venv + app source from the builder
COPY --from=builder --chown=appuser:appuser /app /app

# Put the venv on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

USER appuser
EXPOSE 8000

# Container-level health check (mirrors the ALB/EC2 health check on /health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8000')+'/health').status==200 else 1)"

# Bind to 0.0.0.0 so the container is reachable; uvicorn serves app:app
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
