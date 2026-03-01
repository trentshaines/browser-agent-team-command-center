FROM python:3.12-slim

WORKDIR /app

# Install Node.js (for claude CLI) and uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
    && npm install -g @anthropic-ai/claude-code

COPY . .

RUN uv pip install --system --no-cache .

RUN chmod +x start.sh

CMD ["sh", "start.sh"]
