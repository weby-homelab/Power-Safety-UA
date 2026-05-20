# Release v3.4.11

**Security Hardening (Bookworm Base Image & pip Upgrade)**
В цьому релізі усунено решту вразливостей в базовому образі через перехід на стабільний Debian Bookworm та оновлення інструменту `pip`.

## Що нового / What's New:
🇺🇦 **Українська:**
- Переведено базовий образ на `python:3.12-slim-bookworm` замість звичайного `slim` (який використовує нестабільний Debian Trixie). Це усунуло вразливості в `tar` та `krb5`.
- Додано оновлення `pip` (`pip install --upgrade pip`) перед встановленням залежностей, що усунуло вразливості `CVE-2025-8869`, `CVE-2026-6357` та інші у самому `pip`.

🇬🇧 **English:**
- Switched base image to `python:3.12-slim-bookworm` (eliminating Trixie-based vulnerabilities in `tar` and `krb5`).
- Upgraded `pip` (`pip install --upgrade pip`) to resolve CVEs (`CVE-2025-8869`, `CVE-2026-6357` etc.) in `pip` itself.
