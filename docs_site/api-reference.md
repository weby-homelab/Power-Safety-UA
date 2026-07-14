# API Reference

Power-Safety-UA — FastAPI-застосунок. Інтерактивна документація генерується
**автоматично** (OpenAPI):

- **Swagger UI:** [`/docs`](http://127.0.0.1:5050/docs)
- **ReDoc:** [`/redoc`](http://127.0.0.1:5050/redoc)
- **OpenAPI JSON:** [`/openapi.json`](http://127.0.0.1:5050/openapi.json)

## Основні ендпоінти

| Метод | Шлях | Призначення |
| --- | --- | --- |
| `GET` | `/` | Головна сторінка дашборда (HTML). |
| `GET` | `/health` | Health-check (`{"status":"ok"}`). |
| `GET` | `/health/live` | Liveness-проба (використовується Docker/Cloudflare). |
| `GET` | `/metrics` | Prometheus-метрики. |
| `GET` | `/api/status` | Поточний статус системи. |
| `GET` | `/api/push/{key}` | Heartbeat для Web Push (потребує `SECRET_KEY`). |
| `GET` | `/admin` | Адмін-панель (Glassmorphism). |
| `WS` / `SSE` | `/stream` | Потік оновлень у реальному часі (SSE). |
| `POST` | `/api/telegram/webhook` | Webhook Telegram (перевірка `TELEGRAM_WEBHOOK_SECRET`). |

!!! info "Аутентифікація"
    Публічні ендпоінти захищені rate-limiter (`slowapi`, 120 запитів/хв).
    Адмін- та push-ендпоінти вимагають валідний ключ/підпис.

## Автогенерація документації

- **Swagger / ReDoc** створюються FastAPI автоматично з типів та схем Pydantic.
- Цей сайт документації (MkDocs Material) додано для людей — розгортання,
  конфігурація, операції.
