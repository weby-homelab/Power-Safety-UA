# Changelog / Історія змін (Bilingual/Двомовний)

## [v3.6.1] - 2026-06-10
- **Web Push Notifications:** Підтримка веб-пуш сповіщень через VAPID. / Web Push notification support via VAPID.
- **Годинні AQI стовпчики:** 24 стовпчиків AQI на дашборді. / 24 hourly AQI columns on dashboard.
- **Погодні метрики:** 12 годинних стовпчиків для температури та вологості. / 12 hourly columns for temperature and humidity.
- **5-хвилинні інтервали:** Оптимізовано частоту опитування API до 5 хвилин. / API poll frequency optimized to 5 minutes.

## [v3.6.0] - 2026-06-05
- **Ребрендінг:** Повне перейменування з Flash Monitor Kyiv на Power-Safety-UA. / Full rebranding from Flash Monitor Kyiv to Power-Safety-UA.
- **SEO Metadata:** Оновлено мета-теги та шаблони для нового бренду. / Updated meta tags and templates for new brand.
- **Docker Hub:** Новий образ `webyhomelab/power-safety-ua`. / New Docker Hub image.

## [v3.5.8] - 2026-06-05
- **Локалізація графіків:** Matplotlib звіти адаптовані для двомовності. / Localized daily matplotlib report charts.

## [v3.5.7] - 2026-06-03
- **Захист вводу Admin UI:** Захист полів від авто-оновлення через `document.activeElement`. / Admin UI input protection from auto-refresh.
- **Оптимізація рефрешу:** Зменшено частоту оновлення адмін-панелі. / Slowed down admin UI refresh rate.

## [v3.5.6] - 2026-06-03
- **Фікс збереження конфігу:** Виправлено баг при збереженні конфігурації з адмін-панелі. / Fixed config save bug from admin panel.

## [v3.5.5] - 2026-06-03
- **Синхронізація звітів:** Мінімізовано розрив між полосами в щоденному звіті, синхронізовано тривоги/факт/AQI. / Minimized gap in daily report, synchronized alerts/fact/aqi.

## [v3.5.4] - 2026-06-03
- **10-хвилинні інтервали:** Синхронізація полос звіту до 10-хвилинних інтервалів. / Synchronized report bars to 10-minute intervals.

## [v3.5.3] - 2026-06-03
- **Тижневий AQI фікс:** Фільтрація майбутніх годин AQI в тижневому звіті. / Filter future AQI hours in weekly report.

## [v3.5.2] - 2026-06-03
- **Оптимізація графіків:** Покращено макет щоденного звіту (висота полос, Y-позиції). / Optimized daily report chart layout.

## [v3.5.0] - 2026-06-02
- **Admin Panel:** Glassmorphism веб-інтерфейс для керування системою. / Glassmorphism web interface for system management.
- **Асинхронний кеш:** Новий async caching, що усуває дедлоки. / New async caching eliminating deadlocks.
- **Безпека Zero-Trust:** Захист від LFI (Path Traversal). / LFI (Path Traversal) protection.
- **Healthcheck:** Python-based healthcheck замість curl. / Python-based healthcheck instead of curl.
- **PORT_BINDING:** Гнучке налаштування прив'язки порту через .env. / Flexible port binding via .env.

## [v3.4.10 - v3.4.13] - 2026-05-20
- **CVE Mitigation:** Серія виправлень безпеки Docker-образу (bookworm, purge krb5/tar, pip upgrade). / Docker image security hardening series.

## [v3.4.8 - v3.4.9] - 2026-05-08
- **Кольори тривог:** Виправлено кольори смужок повітряної тривоги на графіках. / Fixed air alert bar colors on charts.
- **Atomic Locks:** Атомарне блокування для генерації звітів. / Atomic locks for report generation.

## [v3.4.4] - 2026-04-23
- **Security:** Оновлено python-dotenv до 1.2.2 (GHSA-mf9w-mj56-hr94). / Updated python-dotenv to fix security advisory.

## [v3.4.0] - 2026-04-22
- **Hardened Release:** Безпека + стабільність + ізоляція середовищ. / Security + stability + environment isolation.
- **Classic branch deprecated:** Bare-metal деплой переведено на Docker. / Bare-metal deployment migrated to Docker.

## [v3.3.6] - 2026-04-07
- **QA & Test Coverage:** Суттєво розширено базу тестів (з 9 до 37). / Significantly expanded test coverage.
- **Анти-спам та Стабільність:** Виправлено баг "холодного старту". / Fixed "cold start" bug.
- **Оптимізація Telegram API:** Інтелектуальна обробка "message is not modified". / Intelligent handling of Telegram errors.
- **Redirect Тестів:** Сповіщення під час "pytest" перенаправлені в приватний чат адміністратора. / Redirected test notifications to admin chat.

## [v3.3.5] - 2026-04-06
- **Дедуплікація Звітів:** Усунуто стан гонитви (race condition). / Resolved race condition.
- **Механізм Блокування:** Впроваджено файлові блокування ".lock" (cooldown 15s). / Added file locking mechanism.
- **Оптимізація Ресурсів:** Поділ логіки генерації щоденних та тижневих звітів. / Optimized report generation.

## [v3.3.4] - 2026-04-05
- **Manual Override Bypass:** Виправлено поведінку ручних команд. / Fixed manual override behavior.
- **Safety Net UI Persistence:** Збільшено таймаут кнопок адмін-панелі до 180 секунд. / Increased admin panel button timeout.
- **Smart Source Logic:** Виправлено відображення джерел на дашборді. / Fixed dashboard source label logic.

## [v3.3.3] - 2026-04-04
- **Smart Anti-Spam:** Розумне дублювання графіків у Telegram. / Implemented smart anti-spam for reports.
- **Data Access Layer:** Атомарні операції з JSON-базами (SafeStateContextAsync). / Atomic operations for JSON database.
- **Notification Service:** Резильєнтний клієнт Telegram. / Resilient Telegram client.
- **Modular State Machine:** Повна асинхронність моніторингу. / Fully asynchronous monitoring.

## [v3.2.0 - v3.3.2]
- Міграція на FastAPI, впровадження Pydantic-моделей, асинхронне I/O, Web Admin Panel (Glassmorphism), інфраструктурні зміни. / Migration to FastAPI, async I/O, Glassmorphism Web UI.
