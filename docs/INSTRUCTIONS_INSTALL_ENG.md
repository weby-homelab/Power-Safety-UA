<p align="center">
  <a href="INSTRUCTIONS_INSTALL_ENG.md">
    <img src="https://img.shields.io/badge/🇬🇧_English-00D4FF?style=for-the-badge&logo=readme&logoColor=white" alt="English README">
  </a>
  <a href="INSTRUCTIONS_INSTALL.md">
    <img src="https://img.shields.io/badge/🇺🇦_Українська-FF4D00?style=for-the-badge&logo=readme&logoColor=white" alt="Українська версія">
  </a>
</p>

<br>

# 🐳 Power-Safety-UA Installation Guide (Docker Edition) [![Latest Release](https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA)](https://github.com/weby-homelab/Power-Safety-UA/releases/latest)

This guide is intended for rapid system deployment using **Docker** and **Docker Compose**. This is the recommended installation method as it provides full dependency isolation and easy updates.

---

## 📌 Requirements
- **Docker** 24.0.0+
- **Docker Compose** v2.20.0+
- OS: Linux (Ubuntu, Debian), macOS, or Windows (WSL2).

---

## 1. Quick Start (One-Step)

If you need a standard configuration, simply download the file and run it:

```bash
# 1. Download docker-compose.yml
curl -O https://raw.githubusercontent.com/weby-homelab/Power-Safety-UA/main/docker-compose.yml

# 2. Run the system in background
docker-compose up -d
```

---

## 2. Environment Configuration (`.env`)

While the system can be configured via the web interface after startup, it is recommended to create a `.env` file for storing sensitive data:

```bash
# Create .env file
nano .env
```

Add the following:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCDefgh...
TELEGRAM_CHANNEL_ID=-100123456789
```

After creating the file, restart the containers:
```bash
docker-compose up -d
```

---

## 3. System Management

| Task | Command |
| :--- | :--- |
| **View Logs** | `docker-compose logs -f` |
| **Update to Latest** | `docker-compose pull && docker-compose up -d` |
| **Stop System** | `docker-compose down` |
| **Restart System** | `docker-compose restart` |

---

## 🔑 Accessing the Admin Panel

After the first run, the system automatically generates an access token. You need to extract it from inside the container:

```bash
docker exec -it power-safety-ua cat data/power_monitor_state.json | grep admin_token
```

Now open your browser:
`http://SERVER_IP:5050/admin?t=YOUR_TOKEN`

---

## 💾 Data Persistence

By default, `docker-compose.yml` creates a volume for the `data/` folder. This means your settings, outage history, and backups **will not disappear** when the container is deleted or updated.

Database files on the host system (if using bind mounts) are typically located in the project folder at `./data`.

---

## 🆘 Troubleshooting

1. **Container not starting:** Check if port 5050 is occupied by another service (`netstat -tulpn | grep 5050`).
2. **Errors in logs:** Run `docker compose logs power-safety-ua-worker` to see parsing or Telegram connection errors.
3. **Image Version:** Ensure you are using the `latest` tag or a specific version (e.g., `v3.4.0`).

---
✦ 2026 Weby Homelab ✦ — modern solutions for energy security.
