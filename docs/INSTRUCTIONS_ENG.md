<p align="center">
  <a href="INSTRUCTIONS_ENG.md">
    <img src="https://img.shields.io/badge/🇬🇧_English-00D4FF?style=for-the-badge&logo=readme&logoColor=white" alt="English README">
  </a>
  <a href="INSTRUCTIONS.md">
    <img src="https://img.shields.io/badge/🇺🇦_Українська-FF4D00?style=for-the-badge&logo=readme&logoColor=white" alt="Українська версія">
  </a>
</p>

<br>

# 🛠 Project Setup Guide: POWER-SAFETY-UA [![Latest Release](https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA)](https://github.com/weby-homelab/Power-Safety-UA/releases/latest)

This guide will help you deploy your own monitoring system from scratch. Follow the steps for the best results.

---

## 1. 🤖 Creating a Telegram Bot

For the system to send reports and notifications, you need your own bot.

1.  Find [@BotFather](https://t.me/botfather) on Telegram.
2.  Send the `/newbot` command and follow the instructions.
3.  **Save the token** (it looks like `123456789:ABCDefgh...`).
4.  Create a **Public Channel** or **Group**.
5.  Add your bot to the channel as an **Administrator**.
6.  Find out your channel ID (use the [@userinfobot](https://t.me/userinfobot) bot or forward a message from the channel to special services). The ID usually starts with `-100...`.

---

## 2. ⚡ Configuring the IoT Sensor (Heartbeat)

The sensor tells the server that "there is light". This can be any device that can make an HTTP request when turned on.

### Option A: ESP32 / ESP8266 (Arduino IDE)
Use this simple code to send a signal every 60 seconds:

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";
const char* serverUrl = "https://your-domain.com/api/push/YOUR_SECRET_KEY";

void setup() {
  WiFi.begin(ssid, password);
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverUrl);
    int httpResponseCode = http.GET();
    http.end();
  }
  delay(60000); // Signal every minute
}
```

---

## 3. 🌐 Configuring Cloudflare Tunnel (Recommended)

For secure access and HTTPS without opening ports:

1.  Install `cloudflared` on your server.
2.  Log in: `cloudflared tunnel login`.
3.  Create a tunnel: `cloudflared tunnel create power-safety-ua`.
4.  Configure `config.yml`:
    ```yaml
    tunnel: <tunnel_id>
    credentials-file: /root/.cloudflared/<tunnel_id>.json
    ingress:
      - hostname: flash.yourdomain.com
        service: http://localhost:5050
      - service: http_status:404
    ```
5.  Run the tunnel: `cloudflared tunnel run power-safety-ua`.

---

## ⚙️ System Configuration (`data/config.json`)

Core settings are now located in the `data/config.json` file. You can manage the system via this file or through the web admin panel. Basic structure example:

```json
{
  "settings": {
    "region": "kyiv",
    "groups": ["GPV36.1"],
    "push_interval": 30,
    "safety_net_timeout": 65
  },
  "sources": {
    "air_quality": {
      "lat": "50.408",
      "lon": "30.400",
      "seb_station": "24185"
    }
  }
}
```

---

## 🎛 Admin Control Panel

Starting from version 2.0, the system features a powerful web-based administration panel.

1.  **Access:** Navigate to your domain at `/admin`.
2.  **Token:** Access requires a secure token. Your unique link is generated automatically. To retrieve it, run:
    ```bash
    cat data/power_monitor_state.json | grep admin_token
    ```
    Your login link will be: `https://your-domain.com/admin?t=YOUR_TOKEN`.
3.  **Features:** Change schedule priority, set report times, edit Telegram notification templates, manage backups, and much more.

---

## 🆘 Troubleshooting

### Images are not updating?
The system uses Cache-Busting. If you see an old image, make sure your browser supports JavaScript and you are using the latest version of the Docker image.

### Bot is not sending messages?
1.  Check if `TELEGRAM_BOT_TOKEN` is correct.
2.  Ensure the bot is an admin in the channel.
3.  Check the logs: `docker logs power-safety-ua-worker` or `journalctl -u power-safety-ua-worker`.

---

## 🛠 Useful Commands

| Action | Command (Docker) | Command (Bare-Metal) |
| :--- | :--- | :--- |
| Restart | `docker compose restart` | `systemctl restart power-safety-ua*` |
| View Logs | `docker compose logs -f` | `tail -f background.log` |
| Update | `docker compose pull && docker compose up -d` | `git pull && pip install -r requirements.txt` |

---
✦ 2026 Weby Homelab ✦  
Built to survive 12h+ blackouts & grid attacks since 2022