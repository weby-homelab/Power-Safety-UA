# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Unified the event visual grammar across reports, the live dashboard, and Telegram: solid fact strips, hatched planned outages, quiet clear states, explicit unknown states, amber warnings, critical red alerts, and thin AQI strips.
- Preserved alert classification, report statistics, Telegram overrides, PWA behavior, and all existing report filenames.

## [3.9.20] - 2026-09-09

### Fixed
- Fixed alert severity classification: drone threats (`"бпла"`, `"дрон"`, `"шахед"`) are now correctly classified as yellow warning level (`ALERT_TYPE_YELLOW`) instead of erroneously triggering red alert (`ALERT_TYPE_RED`).
- Resolved conflict where eTryvoga sent both a drone threat description (`"Загроза застосування БПЛА"`) and a yellow level indicator (`"Жовтий рівень тривоги"`), which previously caused the entire city to be marked as red alert.
- Added comprehensive regression test suite verifying standalone and companion UAV drone threats correctly resolve to yellow warning level.

## [3.9.19] - 2026-09-09

### Fixed
- Strictly isolated air raid alerts, threat levels, and notifications to Kyiv city only (`UID 31`, `м. Київ`), completely ignoring alerts in Kyiv Oblast (`loi: 8`).
- Air raid status, threat levels, and Telegram notifications no longer trigger when alerts sound exclusively in Kyiv Oblast.
- Updated JAAM cross-checks to evaluate strictly Kyiv city status (`is_alert_city`).
- Added comprehensive regression test suite ensuring alerts in Kyiv Oblast do not trigger active state or notifications.

## [3.9.18] - 2026-09-09

### Fixed
- Fixed stale/ghost air raid alerts in Kyiv caused by orphaned records in third-party typed feed (`v3/etryvoga/alerts/active.json`), by introducing a freshness filter (`age > 12h`) in `parse_typed_alerts`.
- Fixed JAAM API integration in `parse_alert_states` to recognize both `"м. Київ"` and `"Київ"` keys, ensuring official DSNS/AFU alerts and clear statuses are accurately detected.
- Added automatic fast cross-check with JAAM when typed feed reports clear, preventing missed or delayed official alerts.
- Sanitized anomalous alert duration calculation in Telegram notifications to prevent announcing obsolete/stale alert durations (> 12 hours).
- Made alert API endpoints (`ALERTS_API_URL`, `TYPED_ALERTS_API_URL`, `JAAM_ALERTS_API_URL`) configurable via environment variables.

### Security
- Patched Trivy code scanning container vulnerabilities by pinning `setuptools>=84.0.0` (CVE-2025-47273, CVE-2026-59890) and `msgpack>=1.2.2` (GHSA-6v7p-g79w-8964) in `Dockerfile` and `requirements.txt`.

### Documentation
- Updated `README.md` and `README_ENG.md` to eliminate documentation drift: added two-tier alert architecture, alerts data sources, notification bell, next-language toggle, SQLite WAL storage, and Prometheus metrics.
- Synchronized supported versions table in `SECURITY.md` and `docs/SECURITY.md` to reflect `v3.9.x`.
- Aligned version references across installation manuals (`docs/INSTRUCTIONS_INSTALL.md`, `docs/INSTRUCTIONS_INSTALL_ENG.md`).

## [3.9.17] - 2026-09-09

### Fixed
- Fixed Service Worker installation failure caused by missing `/static/dashboard_preview.jpg` in cache assets, which caused `navigator.serviceWorker.ready` to hang indefinitely and prevented notification bell UI (`🔕` ➔ `🔔`) from updating.
- Fixed notification toggle button (`#bell-btn`) to provide immediate UI feedback, reliable state persistence, and timeout-protected background push subscriptions.
- Updated language toggle button (`#lang-btn`) to display the NEXT language (EN when page is in Ukrainian, UA when page is in English) with localized tooltips.
- Made Service Worker cache installation resilient against individual asset errors.

## [3.9.16] - 2026-09-09

### Fixed
- Fixed fallback air raid alert sources (JAAM and Ubilling) overriding clear alerts as unknown, allowing proper cancellation and peace status detection when primary alerts.in.ua is unreachable.
- Fixed alert downgrade transition from Red to Yellow in Telegram notifications: now properly announces all-clear for red threat in Ukrainian and notes that yellow warning remains in effect.
- Restored fallback chain execution when typed alert payload fails schema validation.
- Reset stale alert start timestamp upon alert clearance to prevent inflated duration calculations.

## [3.9.15] - 2026-09-08

### Fixed
- Red alert intervals now render after yellow intervals, so immediate danger remains visible when levels overlap in daily and weekly charts.

## [3.9.14] - 2026-09-08

### Fixed
- Added self-healing for missing typed alert history: when live state is red/yellow but explicit history is incomplete, the missing transition is recorded and the daily/weekly charts are refreshed.

## [3.9.13] - 2026-09-08

### Fixed
- Typed red transitions are now recorded even when legacy untyped alert history contains an earlier active event; the dashboard card and daily/weekly graph history stay synchronized.

## [3.9.12] - 2026-09-08

### Fixed
- Restored full-height, full-width alert strips in daily and weekly graphical reports; removed artificial internal lanes and gaps that made yellow/red strips appear narrow and separated.

## [3.9.11] - 2026-09-08

### Added
- Added validated yellow warning-level and red immediate-danger air-raid states from Alerts.in.ua to the live dashboard card.
- Daily and weekly graphical reports now render yellow and red alert intervals with separate legends.
- Immediate Telegram alerts, daily report captions, and weekly summaries now include the alert level.

### Compatibility
- Legacy alert history without an explicit level remains readable and is treated as an official red alert.

## [3.9.5] - 2026-07-12

### Added
- Admin onboarding: on first install the app prints a ready-to-use admin-panel link (`http://localhost:5050/admin?t=<token>`) to the container logs/console exactly once (the token is generated and persisted on first run).
- Admin panel now shows the current admin token next to the "Reset admin token" button, with a **Copy** button (copies the full login link) and an **Open panel** link (opens the admin panel with the token on the current domain) — so the admin can reach the panel from any device/browser.
- `/api/admin/data` (already auth-protected) now returns the full `admin_token` for the authenticated admin.

## [3.9.4] - 2026-07-12

### Fixed
- Dashboard layout regression (v3.9.1–v3.9.3): the CSP `style-src`/`script-src` directives contained a per-request `nonce`, which makes browsers **ignore** `'unsafe-inline'`. As a result all inline `style="..."` attributes and JS-applied styles were blocked, breaking the dashboard layout (AQI number, AQI/temp/hum grid items, air-raid map sizing, mini-graphs). Removed the nonce from the CSP directives so `'unsafe-inline'` takes effect and the layout matches v3.9.0.
- Added `media-src` to the CSP so the notification "ding" sound (`assets.mixkit.co`) is allowed.

## [3.9.2] - 2026-07-09

### Fixed
- Push API (Webhook) section in admin panel now correctly displays URL and secret
- `secret_key` was redacted from `/api/admin/data` response, breaking the admin panel JS

## [3.9.1] - 2026-07-09

### Security
- SSRF fix: `follow_redirects=False` in parser_service (C3)
- Webhook fail-closed: empty `telegram_webhook_secret` returns 503 (H4)
- Admin token: removed `?t=` query param, header-only auth (M9)
- Rate-limit `key_func` now checks `X-Forwarded-For` before `get_remote_address` (M1)
- `load_state()`: `secret_key` init wrapped in `state_mgr` lock (M4)

### Changed
- BackgroundTasks: 11 sync calls migrated to `_safe_send_telegram` / `_safe_send_push_notification` with `asyncio.to_thread` (C2)
- Atomic file writes: temp+os.replace with `chmod 0o600` in all save paths (H1, H5)
- Cache invalidation: `invalidate_config_cache()` called after admin config changes (H3)
- TTL cache (3s) for `/api/status` endpoint reduces blocking file I/O (M2, M3)
- Removed Python SQLite layer: `app/db.py`, `tests/test_db.py`, `aiosqlite` dep (H2)
- Removed unused `pandas`, `numpy` dependencies (M5)
- Fixed `TelegramClient` double-encode of `reply_markup` (M8)
- Added `report_generation_errors` Prometheus metric (M10)

### Logging
- All `print()` calls converted to structlog: 78 occurrences across `app/` and `scripts/` (L1)

### CI/CD
- Added `pytest.ini` with testpaths configuration (M7)
- Coverage gate: 30% → 35% (current coverage 39%) (M6)

## [3.9.0] - 2026-07-08

### Added
- Centralized Prometheus metrics (`app/metrics.py`): HTTP request counters/durations, loop health/restarts, Telegram/push/schedule/air-raid counters
- Exponential backoff on all 4 background loops (`run_loop_with_backoff`, max 300s)
- Graceful shutdown on SIGTERM/SIGINT (`request_shutdown`)
- `/health/worker` endpoint

### Security
- Fix `SafetyNetReactRequest` regex to accept `down`/`tech` actions (safety-net UI was broken)
- Redact `secret_key` and `admin_token` from `/api/admin/data` response
- Add `state_mgr` lock for `event_log.json` writes in `admin_logs_delete`

### Changed
- Migrate 6 blocking TelegramClient calls in webhook to async `_async_telegram_post`
- Wrap `get_air_raid_alert()` in `asyncio.to_thread()` in alerts loop
- Make `admin_service_restart` Docker-aware (no hardcoded systemctl)
- Unify version sources across code, parser, and service worker
- Replace ~97 `print()` calls with structlog across 7 files
- Add `ThreadPoolExecutor(max_workers=4)` replacing `threading.Thread`
- Remove stale module-level TOKEN/CHAT_ID/ADMIN_CHAT_ID snapshots
- Add lazy getter helpers for Telegram config in reports

### CI/CD
- Add `requirements-dev.txt` with pinned dev dependencies
- Add Python 3.13 matrix, bump coverage threshold 30→50
- Add paths-ignore for docs/markdown to skip unnecessary builds
- Add Trivy image scan alongside filesystem scan
- Add anyio thread limiter config (100 threads)

### PWA & A11y
- Remove `user-scalable=no`/`maximum-scale=1.0` from viewport (WCAG 1.4.4)
- Add `<noscript>` fallback
- Fix manifest.json: remove broken `dashboard_preview.jpg`, add `lang`/`categories`
- Add `GZipMiddleware` for HTML compression
- Add `Cache-Control: no-store` to manifest.json and service-worker.js
- Add `/api/version` endpoint
- Add `notificationclose` listener to service worker

### Docs
- Add `CHANGELOG.md` (Keep a Changelog format)
- Add `SECURITY.md`
- Add `CODEOWNERS`

## [3.7.3] - 2026-07-07
### Fixed
- Restore `?t=` query-param support in `/admin` and `check_admin_token`
- Migrate admin.html API calls from `?t=` to `X-Admin-Token` header

## [3.7.2] - 2026-07-07
### Fixed
- CI: `tzdata==2026a` → `2026.2`
- CI: sync ruff version across local/CI
- Restore B404/B603/B607 bandit skips
### Changed
- Bump dependencies: fastapi 0.135.3→0.139.0, numpy 2.1.3→2.5.1, uvicorn 0.34.0→0.50.2, pydantic 2.13.0→2.13.4

## [3.7.1] - 2026-07-06
### Security
- Webhook secret validation (`X-Telegram-Bot-Api-Secret-Token`)
- Path traversal fix (`os.path.basename` + dot detection)
- Token masking (`****XXXX`)
- Rate limiting (slowapi)
- Pydantic validation (8 endpoints migrated from `dict=Body()`)
- SSRF protection (ipaddress module, all private ranges)
- Async HTTP (blocking requests.post → httpx.AsyncClient)
### Docker
- `security_opt: no-new-privileges`, `cap_drop: [ALL]`, `pids_limit: 100`
- `.dockerignore` fixed (`.venv/` excluded)
- SLSA provenance + SBOM generation
- `dependabot.yml`
### Refactoring
- `app/paths.py` — centralized data paths
- `app/config_runtime.py` — cached config with 30s TTL
- `app/reports/` package
- `app/_version.py` — single version source
- `db.py` — `init_db()` runs once
