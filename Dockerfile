FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libpng-dev \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove libkrb5-3 libgssapi-krb5-2 libkrb5support0 libk5crypto3 \
    && dpkg --force-all --purge tar \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p /app/data/static && \
    useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser
EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/health', timeout=5)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5050", "--workers", "4"]
