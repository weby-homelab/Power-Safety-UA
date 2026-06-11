# Security Policy / Політика безпеки

## 🛡️ Security Mandate v4.0 (Zero Trust)

This project operates under a **Zero Trust** architecture. 
As of April 2026, the following rules are strictly enforced:
1. **Zero Hardcoded Secrets:** No API tokens, passwords, or Chat IDs are allowed in the source code.
2. **Environment Isolation:** All configuration must be loaded via `.env` files or system environment variables.
3. **Docker Hygiene:** `.dockerignore` must be used to prevent local configs from leaking into image layers.

---

## Supported Versions / Версії, що підтримуються

| Version | Supported          |
| ------- | ------------------ |
| v3.6.x  | ✅ YES             |
| v3.5.x  | 🛠️ Security Only |
| < v3.5  | ❌ NO              |

---

## Reporting a Vulnerability / Як повідомити про вразливість

**Please do not open public issues for security vulnerabilities.**

If you discover a security leak (exposed tokens, LFI, etc.), please report it directly:
- **Email:** contact@srvrs.top
- **Telegram:** [REDACTED_TG]

We will respond within 24 hours and provide a patch as soon as possible.

## Політика безпеки (UA)

Цей проект дотримується принципу **нульової довіри**. 
- Всі секрети мають зберігатися виключно в `.env` файлах.
- Будь-який витік даних у публічну історію Git призводить до негайної ануляції токенів та переписування історії репозиторію.
- Якщо ви знайшли вразливість — будь ласка, напишіть через офіційні контакти, не створюючи публічний Issue.
