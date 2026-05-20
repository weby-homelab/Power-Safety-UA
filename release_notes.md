# Release v3.4.10

**Security Hardening (CVE Mitigation)**
В цьому релізі усунено критичні вразливості в базовому образі шляхом оновлення пакетів ОС.

## Що нового / What's New:
🇺🇦 **Українська:**
- Оновлено `Dockerfile`: додано `apt-get upgrade -y` для усунення вразливостей в пакетах `krb5` та `glibc` (включаючи CVE-2026-40355, CVE-2026-40356, CVE-2024-26458 та інші).
- Виправлено збірку образу на базі `python:3.12-slim`.

🇬🇧 **English:**
- Updated `Dockerfile`: added `apt-get upgrade -y` to mitigate vulnerability risks in base image OS packages (`krb5`, `glibc` including CVE-2026-40355, CVE-2026-40356, CVE-2024-26458 etc.).
- Fixed Docker image build based on `python:3.12-slim`.
