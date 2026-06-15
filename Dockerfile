FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY core/ ./core/
COPY app/ ./app/

# Install dependencies
RUN uv pip install --system --no-cache .

# Create brain directory
RUN mkdir -p /data/brain

# Environment
ENV ELITE_BRAIN_DIR=/data/brain
ENV ELITE_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# The MCP server uses stdio transport
ENTRYPOINT ["elite-reasoning-mcp"]
