# Getting Started

Цей розділ описує розгортання **Power-Safety-UA (Docker Edition)**.

## Вимоги

- Docker ≥ 24 та Docker Compose v2.
- Linux-сервер (рекомендовано) або будь-яка машина з Docker.
- Telegram Bot Token та Channel ID (для сповіщень).
- Опціонально: Cloudflare Tunnel для безпечного доступу ззовні.

## 1. Клонування та конфігурація

```bash
git clone https://github.com/weby-homelab/Power-Safety-UA.git
cd Power-Safety-UA
cp .env.example .env
```

Відредагуйте `.env` і вкажіть мінімум:

```dotenv
TELEGRAM_BOT_TOKEN="123456:ABC-DEF…"
TELEGRAM_CHANNEL_ID="-1001234567890"
SECRET_KEY="згенеруйте_довгий_випадковий_рядок"
```

!!! warning "Обов'язково встановіть `SECRET_KEY`"
    При запуску `uvicorn --workers 2` кожен воркер згенерує **різний**
    `secret_key`, що спричинить періодичні помилки `403`. Завжди задавайте
    `SECRET_KEY` у `.env` або Docker secrets.

## 2. Запуск

```bash
docker compose up -d
```

Сервіс відкриває порт `5050` (за замовчуванням прив'язаний до `127.0.0.1`).
Перевірте працездатність:

```bash
curl -fsS http://127.0.0.1:5050/health/live
```

## 3. Зовнішній доступ (Cloudflare Tunnel)

Архітектура використовує Cloudflare Tunnel із Zero-Trust та реверс-проксі.
Рекомендується **не** публікувати порт `5050` напряму в інтернет.

## Детальна інструкція

Повну покрокову інструкцію див. у
[INSTRUCTIONS_INSTALL.md](https://github.com/weby-homelab/Power-Safety-UA/blob/main/docs/INSTRUCTIONS_INSTALL.md)
та [INSTRUCTIONS.md](https://github.com/weby-homelab/Power-Safety-UA/blob/main/docs/INSTRUCTIONS.md).

## Оновлення

```bash
docker compose pull
docker compose up -d
```
