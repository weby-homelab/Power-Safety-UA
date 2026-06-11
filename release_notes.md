# Release v3.6.2

**Docker Hub Registry Tag Cleanup Automation**

## Що нового / What's New:
🇺🇦 **Українська:**
- **Скрипт очищення тегів Docker Hub:** Додано Python-скрипт для автоматичного видалення застарілих тегів образів на Docker Hub, зберігаючи лише білий список (`latest`, `main`, `master`, `stable`) та найновішу стабільну версію (semver), що запобігає переповненню та накопиченню старих збірок.

🇬🇧 **English:**
- **Docker Hub tags cleanup script:** Added a Python script to automatically delete outdated image tags on Docker Hub, preserving only whitelisted tags (`latest`, `main`, `master`, `stable`) and the newest stable semver version to prevent registry bloat and accumulation of stale builds.
