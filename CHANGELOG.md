# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.8.0] - 2026-07-07

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
