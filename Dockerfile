FROM python:3.12-slim@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY core/ ./core/
COPY app/ ./app/

# Install the locked runtime environment, including the project itself.
RUN uv sync --frozen --no-dev

# Create brain directory
RUN mkdir -p /data/brain

# Environment
ENV ELITE_BRAIN_DIR=/data/brain
ENV ELITE_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# The MCP server uses stdio transport
ENTRYPOINT ["elite-reasoning-mcp"]
