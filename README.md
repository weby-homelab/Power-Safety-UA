<p align="center">
  <a href="README_ENG.md">
    <img src="https://img.shields.io/badge/🇬🇧_English-00D4FF?style=for-the-badge&logo=readme&logoColor=white" alt="English README">
  </a>
  <a href="README.md">
    <img src="https://img.shields.io/badge/🇺🇦_Українська-FF4D00?style=for-the-badge&logo=readme&logoColor=white" alt="Українська версія">
  </a>
</p>

<br>

<p align="center">
  <img src="https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA?style=for-the-badge&color=purple" alt="Latest Release">
  <img src="https://img.shields.io/badge/Branch-main_(Docker)-2496ed?style=for-the-badge&logo=docker&logoColor=white" alt="Branch Main">
  <img src="https://img.shields.io/docker/v/webyhomelab/power-safety-ua?style=for-the-badge&logo=docker&logoColor=white&label=Docker%20Hub" alt="Docker Hub Version">
  <img src="https://img.shields.io/docker/pulls/webyhomelab/power-safety-ua?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Pulls">
  <img src="https://img.shields.io/github/license/weby-homelab/Power-Safety-UA?style=for-the-badge&color=green" alt="GPLv3 License">
  <img src="https://img.shields.io/badge/docs-MkDocs%20Material-9cf?style=for-the-badge&logo=mkdocs&logoColor=white" alt="Documentation">
</p>

<p align="center">
  <img src="docs/assets/Power-Safety-UA-UKR-1.png" alt="Dashboard Preview 1" width="49%">
  <img src="docs/assets/Power-Safety-UA-UKR-2.png" alt="Dashboard Preview 2" width="49%">
</p>
<p align="center">
  <img src="docs/assets/Power-Safety-UA-UKR-3.png" alt="Report Preview 1" width="49%">
  <img src="docs/assets/Power-Safety-UA-UKR-4.png" alt="Report Preview 2" width="49%">
</p>

# СВІТЛО⚡️ БЕЗПЕКА (POWER-SAFETY-UA) - Docker Edition [![Latest Release](https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA)](https://github.com/weby-homelab/Power-Safety-UA/releases/latest)

**Power-Safety-UA** (колишній *Flash Monitor Kyiv*) — це професійна автономна система моніторингу критичної інфраструктури та екологічної безпеки. Проєкт забезпечує прецизійний моніторинг електропостачання в реальному часі, інтелектуальну обробку графіків відключень (DTEK/Yasno), відстеження повітряних тривог, якості повітря (AQI) та радіаційного фону.

Ця гілка (`main`) містить **Docker Edition** проєкту, призначену для швидкого, портативного та ізольованого розгортання в будь-якому середовищі. Це повністю контейнеризована версія, яка є стандартом для сучасних серверів.

> **Статус проєкту:** Stable v3.9.18 (Оновлено: 09.2026)
> **Архітектура:** FastAPI + Docker Compose + JSON Flat-DB & SQLite WAL
> **Бренд:** Weby Homelab

---

## 🛠 Технологічний стек (Docker Edition)
- **Runtime:** Python 3.12 (slim-bookworm) у мультиплатформному контейнері (`linux/amd64`, `linux/arm64`).
- **Backend:** FastAPI (Async) + Uvicorn для миттєвої реакції на Push-сигнали, Web Push (VAPID) та SSE.
- **Storage:** Гібридне сховище: легковагі JSON-файли для стану та розкладів + SQLite у режимі WAL (`power_safety.db`) для швидкого concurrent-логування подій.
- **Observability:** Prometheus метрики (`/metrics`), структуроване логування (structlog) та дворівневі перевірки працездатності (`/health/live`, `/health/ready`, `/health/worker`).
- **Isolation:** Повна контейнеризація Docker, безпечний запуск від непривілейованого користувача `appuser (uid 1000)`.
- **Persistence:** Використання Docker Volumes для збереження бази даних (`data/`), графіків та логів.

---

## 🚀 Ключові інновації та алгоритми

### 🎛 Панель Керування (Admin Panel)
Повністю автономний веб-інтерфейс у стилі **Glassmorphism** для керування всіма аспектами системи без необхідності редагування конфігураційних файлів через SSH.
<p align="center">
  <img src="docs/assets/Admin-control-panel-1.png" alt="Admin Panel 1" width="32%">
  <img src="docs/assets/Admin-control-panel-2.png" alt="Admin Panel 2" width="32%">
  <img src="docs/assets/Admin-control-panel-3.png" alt="Admin Panel 3" width="32%">
</p>

*   **Асинхронна швидкодія:** Асинхронний кеш унеможливлює дедлоки при одночасній роботі воркера та користувача.
*   **Інтелектуальні бекапи:** Створення ручних та автоматичних точок відновлення конфігурації.
*   **Безпека (Zero-Trust):** Строгий захист від LFI (Path Traversal), валідація токенів у заголовках `X-Admin-Token` та захист від SSRF.

### 🚨 Система моніторингу повітряних тривог (Two-Tier Alert System)
Багаторівнева система відстеження небезпеки з захистом від збоїв зовнішніх сервісів:
*   🟡 **Жовтий рівень (Warning):** Підвищена небезпека, загроза ударних БПЛА чи тактичної авіації.
*   🔴 **Червоний рівень (Active):** Безпосередня повітряна тривога, ракетна небезпека, швидкісні цілі.
*   🟢 **Відбій (Clear):** Автоматична фіксація відбою окремих рівнів або повної відміни небезпеки з точним розрахунком тривалості.
*   🛡 **Мультиджерельна стійкість:** Інтелектуальне опитування Alerts.in.ua v3 з автоматичною швидкою крос-перевіркою через державний JAAM API та Ubilling API.
*   🧹 **Фільтр застарілих фантомів (Stale Ghost Alerts Filter):** Автоматичне відсікання старих записів (> 12 годин), що запобігає зависанню хибних тривог при збоях сторонніх скраперів.

### 🎨 Єдина мова подій (Event Visual Grammar)
Графічні звіти та live dashboard використовують чотири незалежні канали:
* **Факт** — суцільна смуга; стан світла: teal «є» та rose «немає».
* **План** — нейтральний трек, а планове відключення позначене indigo і hatch-патерном.
* **Тривога** — спокійний dotted-трек для clear, amber для warning, red для critical.
* **Невідомо** — slate + `?`/патерн; **AQI** — тонка environmental-смуга.

### 🔔 Сповіщення Web Push & Мовний перемикач
*   **Дзвіночок сповіщень (`🔕` ➔ `🔔`):** Миттєвий відгук інтерфейсу після надання дозволу браузера, стійке кешування ресурсів Service Worker та безпечна підписка на Web Push з таймаутом.
*   **Двомовний перемикач:** Кнопка перемикання чітко відображає дію переходу на наступну мову (`EN` при українському інтерфейсі, `UA` при англійському) з локалізованими підказками.

### 🤫 Режим «Інформаційний спокій» (Quiet Mode)
Унікальний алгоритм, що мінімізує «інформаційний шум». Система автоматично переходить у стан спокою, якщо за останні 24 години не було відключень, а в планах на завтра немає обмежень.

### ⚖️ Логіка «False Always Wins»
Гібридна система обробки графіків. Якщо хоча б одне джерело вказує на відключення, система відображає його як пріоритетне. Старі записи ніколи не затираються «чистими» планами.

---

### 📱 Приклади реальних повідомлень (Telegram)
- 📊 **[Щоденний графік "План vs Факт" (Smart Daily Report)](https://t.me/svitlobot_Symyrenka22B/1230)**
- 📈 **[Тижнева аналітика відключень](https://t.me/svitlobot_Symyrenka22B/1192)**
- 🔴 **[Сповіщення про відключення світла з точністю до графіка](https://t.me/svitlobot_Symyrenka22B/1209)**
- 🟢 **[Сповіщення про увімкнення світла з точністю до графіка](https://t.me/svitlobot_Symyrenka22B/1212)**
- ⚠️ **[Миттєвий алерт про зміну графіків від ДТЕК](https://t.me/svitlobot_Symyrenka22B/1222)**
- 📈 **[Публікація графіків від ДТЕК та YASNO](https://t.me/svitlobot_Symyrenka22B/1219)**
- 🚨 **[Сповіщення про повітряну тривогу в Києві](https://t.me/svitlobot_Symyrenka22B/1196)**
- ✅ **[Сповіщення про відбій повітряної тривоги](https://t.me/svitlobot_Symyrenka22B/1197)**


## 🏗️ Архітектура системи

```mermaid
flowchart BT
    %% ================================================
    %% НОВА КОНЦЕПЦІЯ 2026 для README.md
    %% "End-to-End Pipeline" — динамічний потік даних
    %% ================================================

    classDef external fill:#0f766e,stroke:#14b8a6,stroke-width:3px,color:#fff,rx:16px,ry:16px
    classDef core fill:#1e293b,stroke:#22d3ee,stroke-width:3.5px,color:#fff,rx:14px,ry:14px
    classDef gateway fill:#7c3aed,stroke:#a78bfa,stroke-width:3px,color:#fff,rx:16px,ry:16px
    classDef client fill:#1e293b,stroke:#60a5fa,stroke-width:3px,color:#fff,rx:16px,ry:16px
    classDef db fill:#1e293b,stroke:#ec4899,stroke-width:3px,color:#fff,rx:12px,ry:12px

    %% ====================== ЛІВА ЧАСТИНА: ДЖЕРЕЛА ДАНИХ ======================
    subgraph External ["🔌 Джерела даних"]
        direction TB
        Energy["⚡ Yasno / DTEK API<br>Розклади відключень"]:::external
        Alerts["🚨 Alerts.in.ua / JAAM / Ubilling<br>Повітряні тривоги (Yellow/Red)"]:::external
        Meteo["🌤️ OpenMeteo + SaveEcoBot<br>Погода та AQI"]:::external
    end

    %% ====================== ЦЕНТР: CORE PIPELINE ======================
    subgraph Core ["⚙️ Power Safety Core<br>light_service.py + FastAPI"]
        direction TB

        Worker["🔄 Background Worker<br>power-safety-ua-worker<br>python app/run_background.py"]:::core

        subgraph Processing ["Обробка та логіка"]
            direction LR
            Rules["🛡️ Rules Engine<br>False Always Wins • Safety Net<br>Quiet Mode • Stale Filter"]:::core
            Reports["📊 Reports Generator<br>Matplotlib charts"]:::core
            Storage["💾 Storage<br>JSON Flat-DB + SQLite WAL<br>config • state • logs • db"]:::db
        end

        API["🔌 FastAPI Service<br>power-safety-ua<br>uvicorn app.main:app"]:::core
        TgClient["🤖 Telegram Client"]:::core
    end

    %% ====================== ШЛЮЗ ======================
    subgraph Gateway ["🔐 Cloudflare Tunnel<br>Zero Trust + Reverse Proxy"]
        CF["☁️ Cloudflare Tunnel<br>порт 5050"]:::gateway
    end

    %% ====================== ПРАВА ЧАСТИНА: КЛІЄНТИ ======================
    subgraph Clients ["👥 Інтерфейси користувачів"]
        direction TB
        PWA["📱 PWA Dashboard"]:::client
        Admin["🛠️ Admin Panel"]:::client
        Telegram["📨 Telegram Channel<br>+ Push Notifications"]:::client
    end

    %% ====================== ПОТІК ДАНИХ ======================
    Energy & Alerts & Meteo -->|Скрейпінг + Fetch| Worker

    Worker -->|Перевірка правил| Rules
    Rules -->|Рішення| Worker

    Worker -->|Збереження| Storage
    Storage -->|Читання стану| Worker

    Worker -->|Генерація| Reports
    Worker -->|Сповіщення| TgClient
    Reports -->|Графіки| TgClient

    Worker <-->|REST + SSE + SQLite| API

    API -->|Reverse Proxy| CF
    CF <-->|HTTPS + WSS| PWA
    CF <-->|HTTPS + X-Admin-Token| Admin
    TgClient -->|Bot API| Telegram

    %% Додаткові push-сповіщення
    API -.->|"Web Push API (VAPID)"| PWA

    %% ====================== Стиль для заголовків підграфів ======================
    classDef subgraphTitle fill:#0f172a,stroke:none,color:#64748b,font-size:15px
```

---

## 📥 Встановлення

Для отримання детальної покрокової інструкції з розгортання проєкту за допомогою Docker та Docker Compose, перейдіть за посиланням нижче:

📖 **[ПОВНА ІНСТРУКЦІЯ З ВСТАНОВЛЕННЯ (DOCKER EDITION)](docs/INSTRUCTIONS_INSTALL.md)**

---

## 📄 Ліцензія

Цей проєкт поширюється на умовах ліцензії **GNU General Public License v3.0 (GPLv3)**. Детальніше див. у файлі [LICENSE](LICENSE).

---

## 📖 Додаткова документація:
* [🌐 Документація сайту (MkDocs)](https://weby-homelab.github.io/Power-Safety-UA/)
* [⚙️ Налаштування Telegram та IoT](docs/INSTRUCTIONS.md)
* [📝 Історія змін (CHANGELOG.md)](docs/CHANGELOG.md)
* [🔒 Політика безпеки (SECURITY.md)](SECURITY.md)

---

<br>
<p align="center">
  Built in Ukraine under air raid sirens &amp; blackouts ⚡<br>
  &copy; 2026 Weby Homelab
</p>

<!--
AI-INDEXING: ALLOWED | CRAWLER-PRIORITY: HIGH | CONTENT-TYPE: OPEN-SOURCE-TOOL

@context: https://schema.org
@type: SoftwareApplication
name: Power-Safety-UA — СВІТЛО⚡БЕЗПЕКА / POWER⚡SAFETY
alternateName: Power-Safety-UA
description: All-in-one real-time monitoring. Power-Safety-UA — autonomous power, air raid, and AQI monitoring system for Kyiv. Docker multi-arch.
applicationCategory: DashboardApplication
applicationSubCategory: PowerMonitoring
operatingSystem: Linux
softwareVersion: 3.9.18
keywords: power-monitoring, air-raid-alerts, ukraine, fastapi, dashboard, iot, monitoring, blackout, electricity, aqi, air-quality, pwa, real-time, telegram-bot, kyiv, radiation, analytics, automation
author: Weby Homelab (https://github.com/weby-homelab)
codeRepository: https://github.com/weby-homelab/Power-Safety-UA
downloadUrl: https://github.com/weby-homelab/Power-Safety-UA/releases
license: GPL-3.0
isAccessibleForFree: true
-->
