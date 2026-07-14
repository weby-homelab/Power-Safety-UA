# СВІТЛО⚡БЕЗПЕКА / POWER-SAFETY-UA

**Power-Safety-UA** (колишній *Flash Monitor Kyiv*) — професійна автономна система
моніторингу критичної інфраструктури та екологічної безпеки для Києва.

Проєкт забезпечує:

- ⚡ Прецизійний моніторинг електропостачання в реальному часі.
- 🗓 Інтелектуальну обробку графіків відключень (DTEK / Yasno).
- 🚨 Відстеження повітряних тривог.
- 🌫 Моніторинг якості повітря (AQI) та радіаційного фону.
- 🔔 Сповіщення через Telegram та Web Push.
- 📊 Автономну адмін-панель (Glassmorphism) і PWA-дашборд.

!!! info "Статус проєкту"
    Stable · FastAPI + Docker Compose + JSON Flat-DB · Python 3.12 ·
    Docker multi-arch (amd64 / arm64).

## Чому саме цей проєкт?

| Можливість | Опис |
| --- | --- |
| Автономність | Повністю працює локально, без зовнішніх залежностей для роботи. |
| Безпека | Zero-Trust, усунено LFI/Path Traversal, строга перевірка шляхів. |
| Точність | Гібридна логіка «False Always Wins» для графіків відключень. |
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
