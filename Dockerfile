# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/home/appuser/.local/bin:$PATH"

WORKDIR /app

# System deps (kept minimal; add gcc/headers only if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt ./
RUN pip install --user -r requirements.txt && \
    pip install --user gunicorn

# Copy app
COPY . .

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Default envs for container runtime
ENV FLASK_DEBUG=False \
    SSL_VERIFY=False \
    API_VERSION=10.15 \
    PORT=5001 \
    HOST=0.0.0.0

EXPOSE 5001

# Use gunicorn for production serving
CMD ["/home/appuser/.local/bin/gunicorn", "-b", "0.0.0.0:5001", "app:app", "--workers", "2", "--threads", "4", "--timeout", "60"]

