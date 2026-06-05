<p align="center">
  <a href="INSTRUCTIONS_ENG.md">
    <img src="https://img.shields.io/badge/🇬🇧_English-00D4FF?style=for-the-badge&logo=readme&logoColor=white" alt="English README">
  </a>
  <a href="INSTRUCTIONS.md">
    <img src="https://img.shields.io/badge/🇺🇦_Українська-FF4D00?style=for-the-badge&logo=readme&logoColor=white" alt="Українська версія">
  </a>
</p>

<br>

# 🛠 Інструкція з налаштування проекту СВІТЛО⚡БЕЗПЕКА [![Latest Release](https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA)](https://github.com/weby-homelab/Power-Safety-UA/releases/latest)

Цей посібник допоможе вам розгорнути власну систему моніторингу «з нуля». Дотримуйтесь кроків для досягнення найкращого результату.

---

## 1. 🤖 Створення Telegram Бота

Щоб система могла надсилати звіти та сповіщення, вам потрібен власний бот.

1.  Знайдіть [@BotFather](https://t.me/botfather) у Telegram.
2.  Відправте команду `/newbot` та слідуйте інструкціям.
3.  **Збережіть токен** (виглядатиме як `123456789:ABCDefgh...`).
4.  Створіть **Публічний канал** або **Групу**.
5.  Додайте вашого бота в канал як **Адміністратора**.
6.  Дізнайтеся ID вашого каналу (скористайтеся ботом [@userinfobot](https://t.me/userinfobot) або перешліть повідомлення з каналу в спеціальні сервіси). ID зазвичай починається з `-100...`.

---

## 2. ⚡ Налаштування IoT Датчика (Heartbeat)

Датчик повідомляє серверу, що «світло є». Це може бути будь-який пристрій, що вміє робити HTTP-запит при ввімкненні.

### Варіант А: ESP32 / ESP8266 (Arduino IDE)
Використовуйте цей простий код для надсилання сигналу кожні 60 секунд:

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* ssid = "ВАША_МЕРЕЖА";
const char* password = "ВАШ_ПАРОЛЬ";
const char* serverUrl = "https://your-domain.com/api/push/ВАШ_СЕКРЕТНИЙ_КЛЮЧ";

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
  delay(60000); // Сигнал кожну хвилину
}
```

---

## 3. 🌐 Налаштування Cloudflare Tunnel (Рекомендовано)

Для безпечного доступу та роботи HTTPS без відкриття портів:

1.  Встановіть `cloudflared` на ваш сервер.
2.  Авторизуйтесь: `cloudflared tunnel login`.
3.  Створіть тунель: `cloudflared tunnel create power-safety-ua`.
4.  Налаштуйте `config.yml`:
    ```yaml
    tunnel: <id_тунелю>
    credentials-file: /root/.cloudflared/<id_тунелю>.json
    ingress:
      - hostname: flash.yourdomain.com
        service: http://localhost:5050
      - service: http_status:404
    ```
5.  Запустіть тунель: `cloudflared tunnel run power-safety-ua`.

---

## ⚙️ Конфігурація системи (`data/config.json`)

Основні налаштування тепер знаходяться у файлі `data/config.json`. Ви можете керувати системою як через файл, так і через веб-адмінку. Приклад базової структури:

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

## 🎛 Панель Керування (Admin Dashboard)

Починаючи з версії 2.0, система має потужну веб-панель для адміністрування.

1.  **Вхід:** Перейдіть на ваш домен за адресою `/admin`.
2.  **Токен:** Доступ можливий лише з токеном. Ваше унікальне посилання генерується автоматично. Дізнатися його можна, виконавши команду:
    ```bash
    cat data/power_monitor_state.json | grep admin_token
    ```
    Тоді ваше посилання буде: `https://your-domain.com/admin?t=ВАШ_ТОКЕН`.
3.  **Можливості:** Зміна пріоритету графіків, налаштування часу звітів, редагування шаблонів сповіщень у Telegram, управління бекапами та багато іншого.

---

## 🆘 Пошук та усунення несправностей

### Зображення не оновлюються?
Система використовує Cache-Busting. Якщо ви бачите стару картинку, переконайтеся, що ваш браузер підтримує JavaScript і ви використовуєте останню версію Docker-образу.

### Бот не надсилає повідомлення?
1.  Перевірте правильність `TELEGRAM_BOT_TOKEN`.
2.  Переконайтеся, що бот є адміном у каналі.
3.  Перевірте логи: `docker logs power-safety-ua-worker` або `journalctl -u power-safety-ua-worker`.

---

## 🛠 Корисні команди

| Дія | Команда (Docker) | Команда (Bare-Metal) |
| :--- | :--- | :--- |
| Перезапуск | `docker compose restart` | `systemctl restart power-safety-ua*` |
| Перегляд логів | `docker compose logs -f` | `tail -f background.log` |
| Оновлення | `docker compose pull && docker compose up -d` | `git pull && pip install -r requirements.txt` |

---
✦ 2026 Weby Homelab ✦  
Built to survive 12h+ blackouts & grid attacks since 2022
