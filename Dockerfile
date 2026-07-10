FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY README.md ./
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
