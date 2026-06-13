FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy build files first (README.md required by hatchling via pyproject.toml)
COPY pyproject.toml README.md ./

# Copy source code
COPY core/ ./core/

# Create brain directory
RUN mkdir -p /data/brain

# Install dependencies
RUN uv sync --no-dev --no-cache

# Set environment
ENV ELITE_BRAIN_DIR=/data/brain
ENV PYTHONUNBUFFERED=1

# Run MCP server via stdio
ENTRYPOINT ["uv", "run", "python", "-m", "core.integration.mcp_server"]
