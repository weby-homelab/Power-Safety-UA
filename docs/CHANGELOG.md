# Changelog / Історія змін (Bilingual/Двомовний)

## [v3.9.21] - 2026-09-10
- **Єдина візуальна мова подій (Event & State Visual Identity):** Узгоджено solid Fact, hatched Plan, quiet Clear, explicit Unknown, amber Warning, critical Red і тонку AQI-смугу в daily/weekly reports та live dashboard. / Unified the event grammar across reports and the live dashboard.
- **Сумісність:** Збережено filenames звітів, legacy report statistics, Telegram overrides, PWA behavior і storage/API contracts; додано лише availability metadata для явного Unknown. / Preserved report filenames, legacy statistics, Telegram overrides, PWA behavior, and storage/API compatibility.

## [v3.9.20] - 2026-09-09
- **Класифікація загрози БПЛА як жовтого рівня (Drone Threats Yellow Level Classification):** Виправлено класифікацію загроз: маркери БПЛА (`"бпла"`, `"дрон"`, `"шахед"`) тепер відносяться до жовтого рівня попередження (`ALERT_TYPE_YELLOW`), а не до червоного. Усунено конфлікт, коли одночасне надходження запису загрози БПЛА та жовтого рівня тривоги помилково підвищувало загальний статус міста до червоного рівня. / Reclassified drone threats as yellow warning level instead of red, eliminating false red alerts when yellow UAV warnings are active.
- **Регресійні тести:** Додано перевірки для автономних та комбінованих повідомлень про загрозу БПЛА. / Added regression test coverage for UAV alert levels.

## [v3.9.19] - 2026-09-09
- **Ізоляція тривог для м. Київ (Kyiv City Alerts Isolation):** Забезпечено сувору ізоляцію моніторингу та сповіщень виключно для міста Київ (`UID 31`, `м. Київ`). Тривоги, що лунають лише по Київській області, більше не викликають статус тривоги на дашборді та не надсилають сповіщень до Telegram. / Strictly isolated air raid alerts, threat levels, and Telegram notifications to Kyiv city only, completely ignoring alerts in Kyiv Oblast.
- **Оновлення крос-валідації JAAM:** Перевірка через JAAM API тепер запитує виключно статус міста Київ (`is_alert_city`). / JAAM cross-checks now strictly evaluate Kyiv city status.
- **Регресійні тести:** Додано комплексний набір тестів, що гарантує відсутність хибних спрацьовувань при тривогах в області. / Added regression test suite ensuring alerts in Kyiv Oblast do not trigger active state or notifications.

## [v3.9.18] - 2026-09-09
- **Фільтрація завислих тривог (Stale Alerts Filter):** Виправлено зависання тривоги в Києві через старі неактуальні записи (>12 год) у сторонньому типізованому фіді `v3/etryvoga`. Додано фільтрацію застарілих записів за часом. / Fixed stale/ghost Kyiv air raid alerts caused by orphaned records in third-party typed feed, adding a freshness filter.
- **Підтримка ключів JAAM:** Виправлено розпізнавання ключів `"Київ"` та `"м. Київ"` в API JAAM, що забезпечує точне відстеження офіційних тривог та відбоїв. / Normalized Kyiv keys in JAAM integration to accurately detect official DSNS/AFU alerts and all-clear statuses.
- **Крос-валідація джерел:** Додано швидку перевірку через JAAM у разі відсутності тривоги в типізованому фіді, що запобігає запізненню сповіщень. / Added rapid cross-check with JAAM when typed feed is clear to prevent delayed notifications.
- **Санітизація тривалості тривоги:** Вилучено некоректний розрахунок багатоденної тривалості (>12 год) при відбої застарілих станів у Telegram. / Sanitized anomalous alert duration calculation in Telegram notifications for stale states.
- **Патч безпеки контейнера (Trivy Security):** Оновлено `setuptools>=84.0.0` та `msgpack>=1.2.2` у `Dockerfile` та `requirements.txt` для усунення вразливостей Trivy (CVE-2025-47273, CVE-2026-59890, GHSA-6v7p-g79w-8964). / Patched Trivy container vulnerabilities by upgrading setuptools and msgpack.
- **Синхронізація документації (Docs Drift Elimination):** Оновлено `README.md` та `README_ENG.md` (архітектура тривог, джерела, дзвіночок 🔕 ➔ 🔔, перемикач мов UA/EN, SQLite WAL, Prometheus). Синхронізовано таблиці версій у `SECURITY.md`. / Updated READMEs and security policies to eliminate documentation drift.

## [v3.9.17] - 2026-09-09
- **Значок сповіщень (Bell UI):** Виправлено збій інсталяції Service Worker через відсутній ресурс, що блокувало оновлення значка 🔕 ➔ 🔔. Додано миттєвий відгук UI та захист таймаутом для фонової підписки. / Fixed Service Worker installation failure caused by missing asset, enabling immediate notification bell UI feedback and timeout-protected subscriptions.
- **Перемикач мов (Language switcher):** Значок тепер показує назву наступної мови (EN при активній українській, UA при англійській) з локалізованими підказками. / Language toggle button now shows the next language action (EN when in Ukrainian, UA when in English).
- **Стійкість Service Worker:** Ізольовано завантаження кешу кожного окремого ресурсу. / Made Service Worker cache installation resilient against individual asset errors.

## [v3.9.16] - 2026-09-09
- **Резервні джерела тривог:** Виправлено обробку статусу "відбій" у резервних API (JAAM та Ubilling), щоб відбій коректно фіксувався при недоступності Alerts.in.ua. / Fixed clear alert handling in fallback APIs (JAAM/Ubilling) when primary Alerts.in.ua is unreachable.
- **Сповіщення при переході Red -> Yellow:** Замінено помилковий тривожний банер на коректне повідомлення про відбій червоного рівня українською мовою з нагадуванням про активний жовтий рівень. / Replaced alarming start banner on Red -> Yellow transition with clear notification in Ukrainian.
- **Очищення таймера тривоги:** Скидання застарілого `alert_start_time` при відбої тривоги. / Reset stale alert start timestamp upon alert clearance.

## [v3.9.15] - 2026-09-08
- **Пріоритет red:** Червона смужка тепер рендериться поверх жовтої при перекритті рівнів у денному/тижневому графіку. / Red intervals render above yellow on overlap in daily/weekly charts.

## [v3.9.14] - 2026-09-08
- **Самовідновлення історії:** Якщо live-стан містить red/yellow, а typed-подія відсутня в історії, вона автоматично записується й оновлює графіки. / If live red/yellow state is missing from typed history, the event is recorded and reports are refreshed.

## [v3.9.13] - 2026-09-08
- **Синхронізація рівня:** Typed red transitions більше не блокуються старими безтиповими подіями; карточка та денний/тижневий графік узгоджуються. / Typed red transitions are no longer suppressed by legacy untyped events; card and daily/weekly history stay aligned.

## [v3.9.12] - 2026-09-08
- **Смужки тривог:** Відновлено повну висоту й ширину смужок денного/тижневого звіту, прибрано штучний внутрішній поділ і проміжки. / Restored full-height and full-width daily/weekly alert strips and removed artificial gaps.

## [v3.9.11] - 2026-09-08
- **Рівні тривог:** Жовтий попереджувальний і червоний критичний рівні відображаються окремими кольорами на денних/тижневих графіках та в карточці дашборда. / Yellow warning and red immediate-danger levels render separately in daily/weekly charts and the dashboard card.
- **Telegram:** Рівень додано до миттєвих, щоденних підсумкових і тижневих повідомлень. / Alert levels are included in immediate, daily summary, and weekly Telegram messages.

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
