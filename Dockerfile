FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user and change ownership
RUN addgroup --system appgroup && adduser --system --group appuser \
    && chown -R appuser:appgroup /app

USER appuser

COPY --chown=appuser:appgroup alembic.ini .
COPY --chown=appuser:appgroup migrations /app/migrations
COPY --chown=appuser:appgroup app /app/app

# The command is provided in docker-compose.yml
