<p align="center">
  <a href="INSTRUCTIONS_INSTALL_ENG.md">
    <img src="https://img.shields.io/badge/🇬🇧_English-00D4FF?style=for-the-badge&logo=readme&logoColor=white" alt="English README">
  </a>
  <a href="INSTRUCTIONS_INSTALL.md">
    <img src="https://img.shields.io/badge/🇺🇦_Українська-FF4D00?style=for-the-badge&logo=readme&logoColor=white" alt="Українська версія">
  </a>
</p>

<br>

# 🐳 Інструкція з встановлення Power-Safety-UA (Docker Edition) [![Latest Release](https://img.shields.io/github/v/release/weby-homelab/Power-Safety-UA)](https://github.com/weby-homelab/Power-Safety-UA/releases/latest)

Ця інструкція призначена для швидкого розгортання системи за допомогою **Docker** та **Docker Compose**. Це рекомендований спосіб встановлення, оскільки він забезпечує повну ізоляцію залежностей та простоту оновлення.

---

## 📌 Вимоги
- **Docker** 24.0.0+
- **Docker Compose** v2.20.0+
- ОС: Linux (Ubuntu, Debian), macOS або Windows (WSL2).

---

## 1. Швидкий старт (за один крок)

Якщо вам потрібна стандартна конфігурація, просто завантажте файл та запустіть його:

```bash
# 1. Завантажте docker-compose.yml
curl -O https://raw.githubusercontent.com/weby-homelab/Power-Safety-UA/main/docker-compose.yml

# 2. Запустіть систему в фоновому режимі
docker-compose up -d
```

---

## 2. Налаштування середовища (`.env`)

Хоча систему можна налаштувати через веб-інтерфейс після старту, рекомендується створити файл `.env` для збереження конфіденційних даних:

```bash
# Створіть файл .env
nano .env
```

Впишіть туди наступне:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCDefgh...
TELEGRAM_CHANNEL_ID=-100123456789
```

Після створення файлу перезапустіть контейнери:
```bash
docker-compose up -d
```

---

## 3. Керування системою

| Завдання | Команда |
| :--- | :--- |
| **Переглянути логи** | `docker-compose logs -f` |
| **Оновити до останньої версії** | `docker-compose pull && docker-compose up -d` |
| **Зупинити систему** | `docker-compose down` |
| **Перезапустити** | `docker-compose restart` |

---

## 🔑 Отримання доступу до Адмінки

Після першого запуску система автоматично генерує токен доступу. Його потрібно витягти зсередини контейнера:

```bash
docker exec -it flash-monitor cat data/power_monitor_state.json | grep admin_token
```

Тепер відкрийте браузер:
`http://IP_СЕРВЕРА:5050/admin?t=ВАШ_ТОКЕН`

---

## 💾 Збереження даних (Persistence)

За замовчуванням `docker-compose.yml` створює volume для папки `data/`. Це означає, що ваші налаштування, історія відключень та бекапи **не зникнуть** при видаленні або оновленні контейнера.

Файли бази даних на хост-системі (якщо ви використовуєте bind mount) зазвичай знаходяться в папці проекту за шляхом `./data`.

---

## 🆘 Пошук несправностей

1. **Контейнер не стартує:** Перевірте, чи не зайнятий порт 5050 іншим сервісом (`netstat -tulpn | grep 5050`).
2. **Помилки в логах:** Виконайте `docker-compose logs flash-monitor-worker`, щоб побачити помилки парсингу або підключення до Telegram.
3. **Версія образу:** Переконайтеся, що ви використовуєте тег `latest` або конкретну версію (напр. `v3.4.0`).

---
✦ 2026 Weby Homelab ✦ — сучасні рішення для енергетичної безпеки.
