# Локалізація дашборду та звітів (UA/EN) - План впровадження

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Додати перемикач мов UA|EN біля дзвіночка на дашборді та для PWA, перекласти всі інтерфейси, динамічні дані з API та Matplotlib-графіки для обох тем, підвищити версію до 3.5.8, зібрати Docker-образ та задеплоїти на HTZNR і LXC200.

**Architecture:** 
1. Додаємо перемикач мов на фронтенд із записом обраного стану в localStorage та оновленням DOM-елементів через словник перекладів.
2. Ендпоінт `/api/status` починає приймати параметр `lang` (ua/en) та передавати його для перекладу системних статусів (повітряна тривога, якість повітря, відхилення від графіка).
3. Matplotlib скрипти (`generate_daily_report.py` та `generate_weekly_report.py`) генерують по 4 версії зображень графіків (UA/EN для темної/світлої тем), які зберігаються на сервері як статичні ресурси і підвантажуються фронтендом відповідно до налаштувань.

**Tech Stack:** FastAPI, Jinja2, JavaScript, Matplotlib, Docker, Github API, SSH/pexpect для деплою.

---

### Task 1: Локалізація допоміжних функцій у light_service.py

**Files:**
- Modify: `app/light_service.py`
- Test: `tests/test_light_service.py` (якщо є)

**Step 1: Зміна format_duration**
Оновити `format_duration(seconds)` так, щоб функція приймала `lang='ua'` та повертала англійські позначення одиниць виміру часу (`d`, `h`, `m` замість `д`, `год`, `хв`).

**Step 2: Зміна get_schedule_context**
Оновити `get_schedule_context()` так, щоб функція приймала `lang='ua'` та перекладала текстові повідомлення про прогнозований статус мережі.

**Step 3: Зміна get_deviation_info**
Оновити `get_deviation_info(event_time, is_up)` так, щоб функція приймала `lang='ua'` та повертала локалізовані повідомлення про відхилення від графіку (наприклад, "Powered ON strictly on schedule" / "Увімкнули точно за графіком").

---

### Task 2: Локалізація API у main.py та допоміжних функцій

**Files:**
- Modify: `app/main.py`

**Step 1: Зміна get_wind_label**
Оновити `get_wind_label(deg)` так, щоб функція приймала `lang='ua'` і повертала англійські позначення сторін світу для вітру (`N`, `NE`, `E`, `SE`, `S`, `SW`, `W`, `NW` замість `Пн`, `ПнСх` тощо).

**Step 2: Зміна get_air_quality**
Оновити `get_air_quality()` так, щоб функція приймала `lang='ua'`, перекладала вердикт чистоти повітря (`status_text`), та виконувала кешування у `cached_fetch` під окремим ключем мови: `f"air_quality_{lang}"`.

**Step 3: Зміна get_power_events_data**
Оновити `get_power_events_data(limit=5)` так, щоб функція приймала `lang='ua'` та локалізувала тексти останніх подій (наприклад, "Power restored" / "Світло з'явилося") та відхилень.

**Step 4: Зміна render_day_schedule_html та get_today_schedule_text**
Оновити ці функції, щоб вони приймали `lang='ua'`, перекладали назви місяців, днів тижня та заголовки колонок "Увімкнення"/"Вимкнення".

**Step 5: Оновлення ендпоінту /api/status**
Змінити `@app.get('/api/status')` так, щоб він приймав параметр запиту `lang: str = "ua"` та передавав його у всі вищезазначені функції.

---

### Task 3: Локалізація щоденних Matplotlib звітів

**Files:**
- Modify: `app/generate_daily_report.py`

**Step 1: Зміна generate_chart**
Додати параметр `lang='ua'` у `generate_chart`. Локалізувати осі графіка (`Повітря`/`Air`, `Тривоги`/`Alerts` тощо), заголовок з датою, а також легенду графіку.

**Step 2: Оновлення блоку main**
Оновити скрипт так, щоб при його запуску генерувалися 4 файли звітів:
- `chart.png`, `chart_light.png` (українські)
- `chart_en.png`, `chart_light_en.png` (англійські)
Забезпечити копіювання всіх чотирьох файлів до папки `web_dir` та їхнє видалення з тимчасових папок.

---

### Task 4: Локалізація тижневих Matplotlib звітів

**Files:**
- Modify: `app/generate_weekly_report.py`

**Step 1: Зміна generate_weekly_chart**
Додати параметр `lang='ua'` у `generate_weekly_chart` та локалізувати вісь Y (дні тижня: `Mon`, `Tue` замість `Пн`, `Вт`), заголовок тижневого звіту та легенду.

**Step 2: Оновлення викликів у main**
Оновити генерацію звітів для збереження англійських версій `weekly_en.png` та `weekly_light_en.png` разом з українськими версіями.

---

### Task 5: Фронтенд-компоненти та перемикач мов у index.html

**Files:**
- Modify: `templates/index.html`

**Step 1: Додавання кнопки та стилів**
Додати кнопку перемикання мови (`#lang-btn`) у `header` перед дзвіночком. Додати CSS класи `.lang-btn` для відповідності стилю інтерфейсу.

**Step 2: JS Словник перекладів та applyTranslations()**
Додати об'єкт `translations` та функцію `applyTranslations()`, яка оновлює статичні тексти дашборду.

**Step 3: Передача мови в API та оновлення зображень**
Змінити `update()` для виклику `/api/status?lang=${currentLang}` та `refreshCharts()` для підвантаження зображень з правильними суфіксами (`_en.png`).

---

### Task 6: Випуск версії 3.5.8 та деплой

**Files:**
- Modify: `VERSION`
- Run scripts: `/root/geminicli/build_and_push.py`, `/root/geminicli/deploy_all.py`

**Step 1: Bump версії**
Оновити файл `VERSION` у проекті, встановивши значення `v3.5.8`.

**Step 2: Коміт та Push гілки релізу**
Створити issue через GitHub CLI (або локально git), створити гілку `feature/localization`, закомітити зміни з GPG підписом, запушити та об'єднати гілку через PR.

**Step 3: Збирання та деплой**
Запустити `/root/geminicli/build_and_push.py` для автоматичного збирання образу `webyhomelab/flash-monitor-kyiv:3.5.8` на LXC200 та його пушу в Docker Hub. Після цього запустити `/root/geminicli/deploy_all.py` для оновлення сервісів на HTZNR та LXC200.

**Step 4: Валідація результату**
Здійснити curl запити до обох хостів для перевірки статусу та версії `3.5.8` і перемикання мови.
