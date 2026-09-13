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

# Необов'язково: фіксація точного образу або іммутабельного digest для підвищеної безпеки
# POWER_SAFETY_IMAGE=webyhomelab/power-safety-ua:latest
# POWER_SAFETY_IMAGE=webyhomelab/power-safety-ua@sha256:...
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

Після першого запуску система автоматично генерує токен доступу та виводить у логи безпечний банер із цифровим відбитком (fingerprint) токена (для запобігання витоку секретів у консоль):

```bash
docker-compose logs power-safety-ua 2>&1 | grep -A7 "Перший запуск"
```

У консолі зʼявиться блок вигляду:
```
========================================================================
  Power-Safety-UA: Перший запуск — токен адміна успішно згенеровано.
  Відбиток токена (fingerprint): sha256:1a2b3c4d5e6f7a8b
  Для безпечного доступу скопіюйте токен із файлу стану:
  data/power_monitor_state.json (поле 'admin_token')
  та використовуйте форму входу на сторінці /admin.
========================================================================
```

Для безпеки (Zero-Trust Secret Hygiene) повний токен не друкується у відкритому вигляді в stdout, а надійно зберігається у файлі стану:
```bash
docker exec -it power-safety-ua cat data/power_monitor_state.json | grep admin_token
# або безпосередньо на хості:
grep admin_token data/power_monitor_state.json
```

### Вхід в панель керування:
1. Відкрийте браузер: `http://localhost:5050/admin` (або замініть `localhost:5050` на IP/домен вашого сервера).
2. Введіть отриманий токен у захищену Glassmorphism-картку входу. Токен зберігається виключно в `sessionStorage` браузера та передається через заголовок `X-Admin-Token`.
3. *(Опціонально)*: Ви також можете передати токен через URL-фрагмент `#t=<ВАШ_ТОКЕН>` або параметр `?t=<ВАШ_ТОКЕН>` — система миттєво очистить токен з адресного рядка через `history.replaceState` для збереження конфіденційності.

> 💡 **Підказка:** всередині самої адмінки поточний токен маскується (`admin_token_masked`), а за потреби ви можете згенерувати новий токен натисканням кнопки «Згенерувати новий токен» у розділі безпеки.

---

## 💾 Збереження даних (Persistence)

За замовчуванням `docker-compose.yml` створює volume для папки `data/`. Це означає, що ваші налаштування, історія відключень та бекапи **не зникнуть** при видаленні або оновленні контейнера.

Файли бази даних на хост-системі (якщо ви використовуєте bind mount) зазвичай знаходяться в папці проекту за шляхом `./data`.

---

## 🆘 Пошук несправностей

1. **Контейнер не стартує:** Перевірте, чи не зайнятий порт 5050 іншим сервісом (`netstat -tulpn | grep 5050`).
2. **Помилки в логах:** Виконайте `docker compose logs power-safety-ua-worker`, щоб побачити помилки парсингу або підключення до Telegram.
3. **Версія образу:** Переконайтеся, що ви використовуєте тег `latest` або конкретну версію (напр. `3.9.21`).

---
✦ 2026 Weby Homelab ✦ — сучасні рішення для енергетичної безпеки.
