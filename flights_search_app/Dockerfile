# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080

WORKDIR /app

# Create a non-root user for security best practices on Cloud Run
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Install pinned runtime dependencies reproducibly
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn app.main:api --host 0.0.0.0 --port ${PORT:-8080}"]
