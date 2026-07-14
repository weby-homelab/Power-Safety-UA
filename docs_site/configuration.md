# Configuration

Усі налаштування передаються через змінні середовища (файл `.env` або
Docker secrets у `/run/secrets`).

## Основні

| Змінна | За замовчуванням | Призначення |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — | Токен Telegram-бота. |
| `TELEGRAM_CHANNEL_ID` | — | ID каналу для публікації. |
| `TELEGRAM_WEBHOOK_SECRET` | — | Секрет для перевірки вебхуків. |
| `ADMIN_CHAT_ID` | — | Чат для адміністративних сповіщень. |
| `DATA_DIR` | `data` | Каталог збереження БД/логів. |
| `SECRET_KEY` | — | Секрет сесій/API (обов'язково!). |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` | — | Ключі Web Push (VAPID). |
| `VAPID_CONTACT_EMAIL` | `contact@weby.guru` | Контакт для VAPID. |
| `SCHEDULE_API_URL` | — | Джерело графіків відключень. |
| `ALLOWED_ORIGINS` | `https://power.srvrs.top,http://localhost:5050` | CORS-оріджини (через кому). |
| `PORT_BINDING` | `127.0.0.1` | Прив'язка порту (безпека). |

## Спостережуваність (Observability)

| Змінна | За замовчуванням | Призначення |
| --- | --- | --- |
| `LOG_FORMAT` | `json` | Формат логів: `json` (Loki/ELK) або `console` (dev). |
| `LOG_LEVEL` | `INFO` | Рівень логування (DEBUG/INFO/WARNING/ERROR). |
| `OTEL_ENABLED` | `false` | Увімкнути OpenTelemetry-трасування (`true`/`1`). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318/v1/traces` | OTLP/HTTP endpoint колектора. |
| `OTEL_SERVICE_NAME` | `power-safety-ua` | Ім'я сервісу для колектора. |
| `ENVIRONMENT` | `production` | Середовище розгортання. |

!!! example "Приклад увімкнення трасування"
    ```dotenv
    OTEL_ENABLED=true
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces
    ENVIRONMENT=production
    ```

Докладніше — у розділі [Observability](observability.md).
