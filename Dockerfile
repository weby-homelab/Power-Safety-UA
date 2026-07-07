FROM python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libpng-dev \
    gcc \
    python3-dev \
    && pip install --no-cache-dir --upgrade "pip>=26.1" \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b

LABEL org.opencontainers.image.title="Power-Safety-UA" \
      org.opencontainers.image.description="Autonomous critical infrastructure monitoring system" \
      org.opencontainers.image.vendor="Weby Homelab" \
      org.opencontainers.image.licenses="GPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libfreetype6 \
    libpng16-16 \
    && apt-get purge -y --auto-remove libkrb5-3 libgssapi-krb5-2 libkrb5support0 libk5crypto3 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

RUN mkdir -p /app/data/static && \
    groupadd -r appuser && \
    useradd -r -g appuser -u 1000 --no-log-init --no-create-home -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

USER appuser
EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/health/live', timeout=5)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5050", "--workers", "2"]
