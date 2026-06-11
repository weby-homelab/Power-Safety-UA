# Release v3.6.2

**Docker Hub Registry Tag Cleanup Automation, Rebranding, and Repository Cleanup**

## Що нового / What's New:
🇺🇦 **Українська:**
- **Скрипт очищення тегів Docker Hub:** Додано Python-скрипт (`scripts/delete_dockerhub_tags.py`) для автоматичного видалення застарілих тегів образів на Docker Hub, зберігаючи лише білий список (`latest`, `main`, `master`, `stable`) та найновішу стабільну версію (semver).
- **Ребрендинг Prometheus метрик:** Змінено префікс метрик з `flash_monitor_*` на `power_safety_*` відповідно до поточної назви проєкту.
- **Очищення від застарілих артефактів:** 
  - Видалено застарілі скрипти: `scripts/update_light.py` та `scripts/fix_event_log.py`.
  - Видалено тестові файли: `tests/test_state.py` та `mermaid_schema.txt`.
  - З віддаленого репозиторію остаточно видалено гілку `classic`.
  - Перейменовано файли скріншотів у `docs/assets/` з `Flash-monitor-dash-*` на `power-safety-ua-dash-*` та оновлено посилання в документації.
- **Аудит та виправлення скриптів:**
  - У `scripts/bootstrap.py` додано правильні префікси імпортів (`app.`) для сумісності в Docker.
  - Оновлено `docs/CHANGELOG.md` та `docs/SECURITY.md`.

🇬🇧 **English:**
- **Docker Hub tags cleanup script:** Added a Python script (`scripts/delete_dockerhub_tags.py`) to automatically delete outdated image tags on Docker Hub, preserving only whitelisted tags (`latest`, `main`, `master`, `stable`) and the newest stable semver version.
- **Prometheus metrics rebranding:** Renamed metrics prefix from `flash_monitor_*` to `power_safety_*` to align with the current project name.
- **Outdated artifacts cleanup:**
  - Removed stale scripts: `scripts/update_light.py` and `scripts/fix_event_log.py`.
  - Removed test files: `tests/test_state.py` and `mermaid_schema.txt`.
  - Permanently removed the obsolete `classic` branch from GitHub.
  - Renamed screenshot assets in `docs/assets/` from `Flash-monitor-dash-*` to `power-safety-ua-dash-*` and updated documentation links.
- **Scripts audit & fixes:**
  - Fixed imports in `scripts/bootstrap.py` with `app.` prefix for Docker compatibility.
  - Updated `docs/CHANGELOG.md` and `docs/SECURITY.md`.
