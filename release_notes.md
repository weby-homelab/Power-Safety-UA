# Release v3.7.0

**Security Hardening, SQLite Hybrid Storage, CI/CD Pipeline Upgrades, and Dependency Compatibility Improvements**

## Що нового / What's New:
🇺🇦 **Українська:**
- **Безпека Docker:** Додано безпечний multi-stage build у Dockerfile. Базовий образ запінено за SHA-хешем (`python:3.12-slim-bookworm`). Контейнери тепер запускаються під користувачем `appuser` (non-root) та підтримують повністю read-only файлову систему (`read_only: true` з `tmpfs` для `/tmp`).
- **Гібридне збереження SQLite:** Створено модуль `app/db.py` та інтегровано SQLite (`power_safety.db`). Події тепер дублюються як у `event_log.json`, так і в SQLite.
- **Нові ендпоінти моніторингу:** Додано окремі ендпоінти `/health/live` (перевірка процесу) та `/health/ready` (перевірка доступності сховища).
- **CORS Hardening:** Додано динамічну конфігурацію дозволених CORS доменів через змінну середовища `ALLOWED_ORIGINS`.
- **Покращення CI/CD:** У робочий процес GitHub Actions інтегровано лінтер `Ruff check`, сканер безпеки `Bandit SAST` та автоматичний аналізатор вразливостей `Trivy`.
- **Сумісність з Python 3.13:** Оновлено вимоги у `requirements.txt` (`pandas>=2.2.3`, `numpy>=2.1.0`, `matplotlib>=3.9.0`), які мають офіційну підтримку Python 3.13 та містять готові wheels на PyPI (це прискорює розгортання та усуває помилки компіляції). Оновлено `tzdata==2025.1`.
- **Конфігурація Pydantic:** Налаштовано Pydantic `BaseSettings` для валідації конфігурації.
- **Документація та ліцензія:** Змінено ліцензію на GPLv3. Створено файл `CONTRIBUTING.md` та додано сітку скріншотів дашборду 2х2 в README.

🇬🇧 **English:**
- **Docker Hardening:** Added secure multi-stage build in Dockerfile. Base image is pinned by SHA digest. Containers run as non-root `appuser` and support read-only filesystem with tmpfs.
- **SQLite Hybrid Storage:** Introduced SQLite database (`power_safety.db`). Events are logged side-by-side to JSON flat file and SQLite database.
- **New Monitoring Endpoints:** Implemented `/health/live` and `/health/ready` (storage access check).
- **CORS Hardening:** Enabled dynamic CORS origins configuration via `ALLOWED_ORIGINS` environment variable.
- **CI/CD Pipeline Upgrades:** Integrated `Ruff check` linting, `Bandit` SAST scan, and `Trivy` security scans into GitHub Actions workflow.
- **Python 3.13 Compatibility:** Updated dependencies (`pandas>=2.2.3`, `numpy>=2.1.0`, `matplotlib>=3.9.0`) to versions providing pre-built wheels for Python 3.13. Updated `tzdata==2025.1`.
- **Pydantic Configuration:** Integrated Pydantic `BaseSettings` for robust validation.
- **Open Source Standards:** Migrated license to GPLv3. Added `CONTRIBUTING.md` guide and updated README screenshots with a 2x2 grid.
