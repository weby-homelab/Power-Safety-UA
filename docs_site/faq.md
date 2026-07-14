# FAQ

### Чи можна запустити без Telegram?

Так. Сповіщення через Telegram опціональні. Без `TELEGRAM_BOT_TOKEN` дашборд і
локальний моніторинг працюють, але публікація в канал буде недоступна.

### Чому я бачу періодичні помилки 403?

Через відсутній `SECRET_KEY`. Запуск `uvicorn --workers 2` без нього генерує
різні ключі для кожного воркера. Задайте `SECRET_KEY` у `.env` або Docker
secrets.

### Чи безпечно публікувати порт 5050 у мережу?

Ні, рекомендується Cloudflare Tunnel (Zero-Trust). Контейнер за замовчуванням
прив'язаний до `127.0.0.1`.

### Як увімкнути трасування (OpenTelemetry)?

Встановіть `OTEL_ENABLED=true` та вкажіть `OTEL_EXPORTER_OTLP_ENDPOINT`.
Див. [Observability](observability.md).

### Де подивитися живі метрики?

На `/metrics` (Prometheus). Дашборд — на `/`, адмін-панель — на `/admin`.

### Підтримується лише Київ?

Ядро заточене під Київ (часова зона `Europe/Kyiv`, джерела DTEK/Yasno),
проте архітектура відкрита для розширення іншими регіонами.

### Ліцензія?

GPL-3.0-only. Див. [LICENSE](https://github.com/weby-homelab/Power-Safety-UA/blob/main/LICENSE).
