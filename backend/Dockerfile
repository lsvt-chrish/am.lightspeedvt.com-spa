FROM python:3.12.10-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (via pip to avoid ghcr.io rate limits / auth)
RUN pip install --no-cache-dir uv==0.10.6

# Install dependencies and application (lockfile for reproducible installs)
COPY pyproject.toml uv.lock ./
COPY app/ app/
RUN uv sync --frozen --no-dev

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check: hit /health
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
