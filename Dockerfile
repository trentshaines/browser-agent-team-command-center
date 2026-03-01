FROM python:3.12-slim

WORKDIR /app

# Install Node.js (for claude CLI) + system deps for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
    && npm install -g @anthropic-ai/claude-code

# Copy repo contents
COPY backend/ backend/
COPY scripts/ scripts/
COPY pyproject.toml .

# Install all Python dependencies:
#   backend/ → FastAPI, sqlalchemy, claude-agent-sdk, etc.
#   .        → browser-use, playwright, etc. (root pyproject.toml)
RUN uv pip install --system --no-cache backend/ . \
    && playwright install chromium --with-deps

RUN chmod +x backend/start.sh

WORKDIR /app/backend
CMD ["sh", "start.sh"]
