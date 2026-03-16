FROM python:3.12-slim

# System deps: git (for GitPython clone ops), Node.js (for Claude CLI)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Graceful shutdown support (SIGTERM)
STOPSIGNAL SIGTERM

CMD ["uv", "run", "sweat", "start"]
