# Architecture

Потік даних реалізовано як горизонтальний **End-to-End pipeline**.

```mermaid
flowchart BT
    subgraph External["🔌 Джерела даних"]
        direction TB
        Energy["⚡ Yasno / DTEK API<br>Розклади відключень"]
        Alerts["🚨 Alerts.in.ua / JAAM / Ubilling<br>Повітряні тривоги (Yellow/Red)"]
        Meteo["🌤️ OpenMeteo + SaveEcoBot<br>Погода та AQI"]
    end

    subgraph Core["⚙️ Power Safety Core"]
        direction TB
        Worker["🔄 Background Worker<br>run_background.py"]
        subgraph Processing["Обробка та логіка"]
            direction LR
            Rules["🛡️ Rules Engine<br>False Always Wins • Safety Net<br>Quiet Mode • Stale Filter"]
            Reports["📊 Reports Generator<br>Matplotlib charts"]
            Storage["💾 Storage<br>JSON Flat-DB + SQLite WAL<br>config • state • logs • db"]
        end
        API["🔌 FastAPI Service<br>app.main:app"]
        TgClient["🤖 Telegram Client"]
    end

    subgraph Gateway["🔐 Cloudflare Tunnel"]
        CF["☁️ Cloudflare Tunnel<br>порт 5050"]
    end

    subgraph Clients["👥 Інтерфейси"]
        direction TB
        PWA["📱 PWA Dashboard"]
        Admin["🛠️ Admin Panel"]
        Telegram["📨 Telegram Channel"]
    end

    Energy & Alerts & Meteo -->|Скрейпінг + Fetch| Worker
    Worker -->|Перевірка правил| Rules
    Worker -->|Збереження| Storage
    Worker -->|Генерація| Reports
    Worker -->|Сповіщення| TgClient
    Worker <-->|REST + SSE + SQLite| API
    API -->|Reverse Proxy| CF
    CF <-->|HTTPS + SSE| PWA
    CF <-->|HTTPS + X-Admin-Token| Admin
    TgClient -->|Bot API| Telegram
```

## Компоненти

| Компонент | Файл | Роль |
| --- | --- | --- |
| API | `app/main.py` | FastAPI, ендпоінти, middleware, SSE. |
| Worker | `app/run_background.py` | Фоновий цикл опитування джерел. |
| Rules Engine | `app/light_service.py` | Логіка графіків, Quiet Mode, Safety Net, тривоги. |
| Storage | `app/storage.py` | Гібридне сховище: JSON Flat-DB + SQLite WAL. |
| Parser | `app/parser_service.py` | Парсинг графіків DTEK/Yasno. |
| Telegram | `app/telegram_client.py` | Публікація сповіщень. |
| Push | `app/push_service.py` | Web Push (VAPID). |
| Observability | `app/observability.py` | Структуровані логи + OpenTelemetry. |
| Metrics | `app/metrics.py` | Prometheus-метрики. |

## Безпека контейнерів

`docker-compose.yml` застосовує: `no-new-privileges`, `cap_drop: ALL`,
`read_only: true`, `tmpfs`, не-root користувач `1000:1000`, обмеження ресурсів
CPU/RAM та healthcheck.
