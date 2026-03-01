FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY . .

RUN uv pip install --system --no-cache .

RUN chmod +x start.sh

CMD ["sh", "start.sh"]
