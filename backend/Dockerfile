FROM python:3.12-slim

WORKDIR /app

# Install Node.js (for claude CLI) + system deps
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv \
    && npm install -g @anthropic-ai/claude-code

COPY . .

# Install Python deps (includes browser-use, playwright via pyproject.toml)
ENV PLAYWRIGHT_BROWSERS_PATH=/app/pw-browsers
# Pass --build-arg INSTALL_BROWSERS=true to install Chromium for local browser mode.
# Omit (default) when using BROWSER_USE_CLOUD=1 to keep the image ~500MB lighter.
ARG INSTALL_BROWSERS=false
RUN uv pip install --system --no-cache . \
    && if [ "$INSTALL_BROWSERS" = "true" ]; then playwright install chromium --with-deps; fi

RUN chmod +x start.sh

# claude CLI refuses --dangerously-skip-permissions as root
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["sh", "start.sh"]
