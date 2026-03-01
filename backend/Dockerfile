FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy dependency manifest first (cache layer)
COPY pyproject.toml .

# Install dependencies
RUN uv pip install --system --no-cache .

# Copy application code
COPY . .

# Railway injects $PORT at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
