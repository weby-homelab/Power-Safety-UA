# СВІТЛО⚡БЕЗПЕКА / POWER-SAFETY-UA

**Power-Safety-UA** (колишній *Flash Monitor Kyiv*) — професійна автономна система
моніторингу критичної інфраструктури та екологічної безпеки для Києва.

Проєкт забезпечує:

- ⚡ Прецизійний моніторинг електропостачання в реальному часі.
- 🗓 Інтелектуальну обробку графіків відключень (DTEK / Yasno).
- 🚨 Відстеження повітряних тривог (жовтий/червоний рівні, загрози БПЛА/балістики/авіації).
- 🔇 Режим спокою (Quiet Mode) з повним глушінням тривог під час стабільної мережі.
- 🌫 Моніторинг якості повітря (AQI) та радіаційного фону (резервування SaveEcoBot).
- 🔔 Сповіщення через Telegram та Web Push.
- 📊 Автономну адмін-панель (Glassmorphism з токен-автентифікацією) і PWA-дашборд.

!!! info "Статус проєкту"
    Stable (v3.9.27) · FastAPI + Docker Compose + JSON Flat-DB + SQLite WAL · Python 3.12 ·
    Docker multi-arch (amd64 / arm64).

## Чому саме цей проєкт?

| Можливість | Опис |
| --- | --- |
| Автономність | Повністю працює локально, без зовнішніх залежностей для роботи. |
| Безпека | Zero-Trust, усунено LFI/Path Traversal, авторизація через `X-Admin-Token` та заголовок Bearer. |
| Точність | Гібридна логіка «False Always Wins» для графіків відключень. |
| Спокій | Інтелектуальний Quiet Mode: глушіння сповіщень про тривоги та відключення при стабільній мережі. |
| Надійність | Гібридне сховище JSON Flat-DB + SQLite WAL, персистентність звітів із блокуванням `fcntl.flock`. |
| Спостережуваність | Prometheus-метрики, структуровані JSON-логи, опціональний OpenTelemetry. |

## Швидкий старт

```bash
git clone https://github.com/weby-homelab/Power-Safety-UA.git
cd Power-Safety-UA
cp .env.example .env   # заповніть TELEGRAM_BOT_TOKEN, SECRET_KEY, …
docker compose up -d
```

Детальніше — у розділі [Getting Started](getting-started.md).

## Навігація

- [Getting Started](getting-started.md) — повне розгортання через Docker.
- [Configuration](configuration.md) — усі змінні середовища.
- [Observability](observability.md) — логи, метрики, трасування.
- [API Reference](api-reference.md) — endpoints, Swagger, ReDoc.
- [Architecture](architecture.md) — схема потоку даних.
- [Contributing](contributing.md) — як зробити внесок.
- [FAQ](faq.md) — поширені питання.
