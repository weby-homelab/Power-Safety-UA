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
</p>

<p align="center">
  <img src="docs/assets/Flash-monitor-dash-ENG.png" alt="Dashboard Preview" width="100%">
</p>

# POWER⚡️ SAFETY (POWER-SAFETY-UA) - Docker Edition [![Latest Release](https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA)](https://github.com/weby-homelab/Power-Safety-UA/releases/latest)

**Power-Safety-UA** (formerly *Flash Monitor Kyiv*) is a professional autonomous monitoring system for critical infrastructure and environmental safety. The project provides precision real-time electricity monitoring, intelligent outage schedule processing (DTEK/Yasno), air raid alert tracking, air quality (AQI), and radiation background levels.

This branch (`main`) contains the **Docker Edition** of the project, designed for fast, portable, and isolated deployment in any environment. It is a fully containerized version, which is the industry standard for modern server deployments.

> **Project Status:** Stable v3.6.0 (Updated: 06.2026)
> **Architecture:** FastAPI + Docker Compose + JSON Flat-DB
> **Brand:** Weby Homelab

---

## 🛠 Technology Stack (Docker Edition)
- **Runtime:** Python 3.12 (slim-bookworm) inside a container.
- **Backend:** FastAPI (Async) for near-instant reaction to Push signals and SSE.
- **Isolation:** Complete dependency isolation, preventing conflicts with host system packages.
- **Persistence:** Docker Volumes ensure database (`data/`) and logs preservation.

---

## 🚀 Core Innovations & Algorithms

### 🎛 Admin Control Panel
A fully autonomous **Glassmorphism** web interface to manage all system aspects without the need for SSH or direct configuration file editing.
<p align="center">
  <img src="docs/assets/Admin-control-panel-1.png" alt="Admin Panel 1" width="32%">
  <img src="docs/assets/Admin-control-panel-2.png" alt="Admin Panel 2" width="32%">
  <img src="docs/assets/Admin-control-panel-3.png" alt="Admin Panel 3" width="32%">
</p>

*   **Asynchronous Performance:** A new async caching mechanism eliminates deadlocks between the background worker and user requests.
*   **Smart Backups:** Create manual and automatic restoration points.
*   **Security (Zero-Trust):** Implements strict Path Traversal protection and secure path validation.

### 🤫 «Quiet Mode» (Information Calm)
A unique algorithm that minimizes "information noise." The system automatically enters a calm state if no outages occurred in the last 24 hours and no restrictions are planned for the upcoming day.

### ⚖️ «False Always Wins» Logic
A hybrid schedule processing system. If at least one source indicates an outage, the system prioritizes it. Historical records are never overwritten by "clean" plans.

---


### 📱 Real Message Examples (Telegram)
- 📊 **[Daily "Plan vs Fact" Chart (Smart Daily Report)](https://t.me/svitlobot_Symyrenka22B/1230)**
- 📈 **[Weekly outage analytics](https://t.me/svitlobot_Symyrenka22B/1192)**
- 🔴 **[Outage notification with schedule accuracy](https://t.me/svitlobot_Symyrenka22B/1209)**
- 🟢 **[Restoration notification with schedule accuracy](https://t.me/svitlobot_Symyrenka22B/1212)**
- ⚠️ **[Instant alert about DTEK schedule change](https://t.me/svitlobot_Symyrenka22B/1222)**
- 📈 **[Publication of DTEK and YASNO schedules](https://t.me/svitlobot_Symyrenka22B/1219)**
- 🚨 **[Air raid alert in Kyiv](https://t.me/svitlobot_Symyrenka22B/1196)**
- ✅ **[Air raid all-clear notification](https://t.me/svitlobot_Symyrenka22B/1197)**


## 🏗️ System Architecture

```mermaid
flowchart BT
    %% ================================================
    %% NEW CONCEPT 2026 for README.md
    %% "End-to-End Pipeline" — dynamic data flow
    %% Horizontal pipeline with clear direction
    %% Clean, modern, easy to read in GitHub (dark/light themes)
    %% ================================================

    classDef external fill:#0f766e,stroke:#14b8a6,stroke-width:3px,color:#fff,rx:16px,ry:16px
    classDef core fill:#1e293b,stroke:#22d3ee,stroke-width:3.5px,color:#fff,rx:14px,ry:14px
    classDef gateway fill:#7c3aed,stroke:#a78bfa,stroke-width:3px,color:#fff,rx:16px,ry:16px
    classDef client fill:#1e293b,stroke:#60a5fa,stroke-width:3px,color:#fff,rx:16px,ry:16px
    classDef db fill:#1e293b,stroke:#ec4899,stroke-width:3px,color:#fff,rx:12px,ry:12px

    %% ====================== LEFT SIDE: DATA SOURCES ======================
    subgraph External ["🔌 Data Sources"]
        direction TB
        Energy["⚡ Yasno / DTEK API<br>Outage Schedules"]:::external
        Meteo["🌤️ OpenMeteo + SaveEcoBot<br>Weather & AQI"]:::external
    end

    %% ====================== CENTER: CORE PIPELINE ======================
    subgraph Core ["⚙️ Power Safety Core<br>light_service.py + FastAPI"]
        direction TB

        Worker["🔄 Worker<br>power-safety-ua-worker.service"]:::core

        subgraph Processing ["Processing & Logic"]
            direction LR
            Rules["🛡️ Rules Engine<br>False Always Wins • 30s Safety Net<br>Quiet Mode"]:::core
            Reports["📊 Reports Generator<br>Matplotlib charts"]:::core
            Storage["💾 Storage<br>JSON Flat-DB<br>config • state • logs • schedules"]:::db
        end

        API["🔌 FastAPI<br>power-safety-ua.service<br>app.py"]:::core
        TgClient["🤖 Telegram Client"]:::core
    end

    %% ====================== GATEWAY ======================
    subgraph Gateway ["🔐 Cloudflare Tunnel<br>Zero Trust + Reverse Proxy"]
        CF["☁️ Cloudflare Tunnel<br>port 5050"]:::gateway
    end

    %% ====================== RIGHT SIDE: CLIENTS ======================
    subgraph Clients ["👥 User Interfaces"]
        direction TB
        PWA["📱 PWA Dashboard"]:::client
        Admin["🛠️ Admin Panel"]:::client
        Telegram["📨 Telegram Channel<br>+ Push Notifications"]:::client
    end

    %% ====================== DATA FLOW (Main Trunk) ======================
    Energy & Meteo -->|Scraping + Fetch| Worker

    Worker -->|Rules Check| Rules
    Rules -->|Decision| Worker

    Worker -->|Storage| Storage
    Storage -->|Read State| Worker

    Worker -->|Generation| Reports
    Worker -->|Notifications| TgClient
    Reports -->|Charts| TgClient

    Worker <-->|REST + WebSocket| API

    API -->|Reverse Proxy| CF
    CF <-->|HTTPS + JWT / WSS| PWA
    CF <-->|HTTPS + JWT| Admin
    TgClient -->|Bot API| Telegram

    %% Additional push notifications
    API -.->|Web Push API| PWA

    %% ====================== Subgraph Title Style ======================
    classDef subgraphTitle fill:#0f172a,stroke:none,color:#64748b,font-size:15px
```

---

## 📥 Installation

For a detailed step-by-step guide on deploying the project using Docker and Docker Compose, please follow the link below:

📖 **[FULL INSTALLATION GUIDE (DOCKER EDITION)](docs/INSTRUCTIONS_INSTALL.md)**

---

📖 **Additional Documentation:**
* [⚙️ Telegram & IoT Setup](docs/INSTRUCTIONS.md)
* [📝 Change History (CHANGELOG.md)](docs/CHANGELOG.md)

---

<br>
<p align="center">
  Built in Ukraine under air raid sirens &amp; blackouts ⚡<br>
  &copy; 2026 Weby Homelab
</p>
