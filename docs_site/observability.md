# Observability

Power-Safety-UA надає три рівні спостережуваності: **метрики**, **логи** та
**трасування** (distributed tracing).

## Метрики (Prometheus)

Експортуються на ендпоінті `/metrics` у форматі Prometheus:

- `power_http_requests_total{method,endpoint,status}`
- `power_http_request_duration_seconds{method,endpoint}`
- `power_safety_active_sse_connections`
- `power_telegram_messages_total{type}`
- `power_air_raid_alerts_total{status}`
- `power_loop_health{loop_name}`
- …та інші.

Підключіть Prometheus / Grafana до `http://host:5050/metrics`.

## Логи (структуровані)

За замовчуванням логи виводяться у **JSON** (один об'єкт на рядок) —
ідеально для [Loki](https://grafana.com/oss/loki/) або ELK.

```json
{"event": "request_handled", "request_id": "a1b2…", "method": "GET",
 "path": "/api/status", "status": 200, "duration_ms": 4.21,
 "level": "info", "timestamp": "2026-07-14T12:00:00.123456+00:00"}
```

Кожен запит отримує `request_id`, а за увімкненого трасування — також
`trace_id` (через `structlog` contextvars), що дозволяє корелювати логи зі
спенами.

```dotenv
LOG_FORMAT=json      # або console для локальної розробки
LOG_LEVEL=INFO
```

## Трасування (OpenTelemetry)

Опціонально. Увімкніть, щоб надсилати спени до OTLP-сумісного колектора
(OpenTelemetry Collector, Tempo, Jaeger, Grafana Cloud):

```dotenv
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
OTEL_SERVICE_NAME=power-safety-ua
ENVIRONMENT=production
```

- Трасування використовує **OTLP/HTTP** експортер (`/v1/traces`).
- Бібліотеки імпортуються *ліниво*: якщо `OTEL_ENABLED=false`, додаток
  працює без них.
- Додається ресурс із `service.name`, `service.version` та
  `deployment.environment`.
- Middleware трасування — **raw ASGI**, тому не ламає SSE-стрімінг дашборда.

!!! tip "Self-hosted Collector"
    Мінімальний endpoint — `http://localhost:4318/v1/traces` (OpenTelemetry
    Collector з OTLP HTTP receiver). Для Grafana Tempo використовуйте той самий
    протокол.

## Observability у адмін-панелі

Без зовнішнього пайплайну (Loki/Jaeger) останні події та агреговану
статистику можна бачити просто в **адмін-панелі** (`/admin`), у секції
**Observability**:

- картки з кількістю `5xx` / `4xx` помилок, середнім та `P95` часом відгуку,
  загальною кількістю запитів і статусом трасування OTel;
- таблиця останніх HTTP-запитів (час, метод, шлях, статус, тривалість,
  `request_id`).

Дані беруться зі структурованих логів (`app/observability.py`) і зберігаються
**в оперативній пам'яті** — вони обнуляються після рестарту застосунку. Для
довгострокового зберігання та алертингу використовуйте Loki/ELK + Grafana.

Ендпоінт: `GET /api/admin/observability` (захищений `X-Admin-Token`).
