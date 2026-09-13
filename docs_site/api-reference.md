# API Reference

Power-Safety-UA — FastAPI-застосунок. Інтерактивна документація генерується
**автоматично** (OpenAPI):

- **Swagger UI:** [`/docs`](http://127.0.0.1:5050/docs)
- **ReDoc:** [`/redoc`](http://127.0.0.1:5050/redoc)
- **OpenAPI JSON:** [`/openapi.json`](http://127.0.0.1:5050/openapi.json)

## Основні ендпоінти

| Метод | Шлях | Призначення |
| --- | --- | --- |
| `GET` | `/` | Головна сторінка дашборда (HTML / PWA). |
| `GET` | `/admin` | Адмін-панель керування (Glassmorphism). |
| `GET` | `/health` | Базовий health-check (`{"status":"ok"}`). |
| `GET` | `/health/live` | Liveness-проба (використовується Docker/Cloudflare). |
| `GET` | `/health/ready` | Readiness-проба готовності сервісу. |
| `GET` | `/health/worker` | Перевірка стану фонового воркера. |
| `GET` | `/metrics` | Prometheus-метрики застосунку. |
| `GET` | `/api/version` | Поточна версія релізу системи. |
| `GET` | `/api/status` | Поточний стан світла, графіків та тривог (JSON). |
| `GET` | `/api/status/stream` | Потік оновлень у реальному часі через Server-Sent Events (SSE). |
| `GET` | `/api/push/{key}` | Heartbeat присутності мережі від IoT-датчика (потребує `SECRET_KEY`). |
| `GET` | `/api/ping/{key}` | Альтернативний endpoint перевірки доступності. |
| `GET` | `/api/down/{key}` | Прямий сигнал відключення живлення (потребує `SECRET_KEY`). |
| `GET` | `/api/confirm-outage/{action}/{key}` | Підтвердження відключення (Safety Net). |
| `GET` | `/api/push/vapid-key` | Отримання публічного VAPID-ключа для Web Push. |
| `POST` | `/api/push/subscribe` | Реєстрація підписки браузера на Web Push. |
| `POST` | `/api/push/unsubscribe` | Скасування підписки Web Push. |
| `POST` | `/api/tg/webhook` | Webhook для отримання оновлень від Telegram Bot API. |
| `GET` | `/api/admin/data` | Дані стану для адмін-панелі (`X-Admin-Token`). |
| `POST` | `/api/admin/config` | Збереження налаштувань системи (`X-Admin-Token`). |
| `GET` | `/api/admin/observability` | Метрики та останні логи в реальному часі (`X-Admin-Token`). |

!!! info "Аутентифікація та безпека"
    - Публічні ендпоінти захищені rate-limiter (`slowapi`, 120 запитів/хв).
    - IoT-ендпоінти (`/api/push/{key}`, `/api/down/{key}`) вимагають співпадіння з `SECRET_KEY`.
    - Telegram webhook перевіряє заголовок `X-Telegram-Bot-Api-Secret-Token` проти `TELEGRAM_WEBHOOK_SECRET`.
    - Адмін-ендпоінти вимагають автентифікацію через заголовок `X-Admin-Token` або `Authorization: Bearer <token>`.

## Автогенерація документації

- **Swagger / ReDoc** створюються FastAPI автоматично з типів та схем Pydantic.
- Цей сайт документації (MkDocs Material) додано для людей — розгортання,
  конфігурація, операції.
