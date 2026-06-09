FROM python:3.11-slim

# Install uv
RUN pip install uv

# /workspace/conversational/ is the package root.
# PYTHONPATH=/workspace lets Python resolve "import conversational".
WORKDIR /workspace/conversational

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies into the isolated venv
RUN uv sync --no-dev --frozen

# Copy application source
COPY . .

# Make 'import conversational' work at runtime
ENV PYTHONPATH=/workspace

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "conversational.main:app", "--host", "0.0.0.0", "--port", "8001"]
