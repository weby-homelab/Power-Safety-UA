# Release v3.9.4

**Dashboard layout fix (CSP regression)**

## What's Fixed
- The dashboard layout broke in v3.9.1–v3.9.3 because the Content-Security-Policy `style-src`/`script-src`
  carried a per-request `nonce`. Per the CSP spec, when a nonce is present `'unsafe-inline'` is ignored,
  so every inline `style="..."` attribute and JS-applied style was blocked by the browser.
- Symptoms: tiny AQI number, unstyled AQI/temp/hum grid items, wrong air-raid map sizing, broken mini-graphs.
- Fix: dropped the nonce from `style-src`/`script-src` (kept `'unsafe-inline'`), so inline styles/JS are
  allowed again — the dashboard now renders identically to v3.9.0.
- Added `media-src` so the Web Push "ding" sound is permitted.

### 🐳 Docker
- Image rebuilt and published as `webyhomelab/power-safety-ua:3.9.4` (and `:3.9`, `:latest`).

# Release v3.9.0

**Performance, Reliability & Observability Improvements**

## What's New:

### 📊 Centralized Metrics (app/metrics.py)
- HTTP request duration & counters (power_http_requests_total, power_http_request_duration_seconds)
- Loop health gauge + restart counters (power_loop_health, power_loop_restarts_total)
- Telegram message/error counters (power_telegram_messages_total, power_telegram_errors_total)
- Schedule sync & air raid alert counters (power_schedule_syncs_total, power_air_raid_alerts_total)
- Metadata info gauge (version, role)

### 🔄 Exponential Backoff for All Background Loops
- monitor_loop, alerts_loop, schedule_loop, metrics_collector_loop
- Exponential backoff to 300s max on failure
- loop_health gauge: 1=healthy, 0=down/restarting
- Graceful shutdown via SIGTERM/SIGINT handlers (both API and worker containers)

### 🗄️ SQLite WAL Mode (app/db.py)
- PRAGMA journal_mode=WAL — better concurrent performance
- PRAGMA synchronous=NORMAL — balance of speed and durability
- PRAGMA busy_timeout=5000 — 5s timeout for locked DB
- vacuum_db() support for periodic maintenance
- event_log_errors Prometheus counter

### 🐳 Docker Improvements
- Worker healthcheck: checks power_safety.db file existence
- stop_grace_period: 30s for both containers (graceful shutdown)
- Removed pids_limit (conflict with Docker Compose v2.40.3)
- Added localhost:5050 to default ALLOWED_ORIGINS

### 🕸️ HTTP Request Duration Middleware
- All API endpoints now auto-measured for duration

### 🧪 18 New Tests (total: 107)
- CircuitBreaker, ScheduleChangeDetection, SSRFBlocklist
- LoopBackoff, HealthEndpoints with new metrics

### 📊 Stats
- Files changed: 11 (4 new, 7 modified)
- Lines added: 541, removed: 216
- Tests: 107/108 passing (1 pre-existing mock scope issue)
- Ruff: clean, Bandit: 0 new issues

---

# Release v3.8.0

**Comprehensive Security, Architecture & PWA Improvements**

## What's New:

### 🔒 Security Fixes (C1-C7)
- **C1:** Fix SafetyNetReactRequest regex to accept `down`/`tech` actions (safety-net UI was broken)
- **C2:** Redact `secret_key` and `admin_token` from admin API response (were leaking secrets)
- **C3:** Add file lock for `event_log.json` writes in concurrent container scenario
- **C4:** Migrate 6 blocking TelegramClient calls in webhook to async `_async_telegram_post`
- **C5:** Wrap `get_air_raid_alert()` in `asyncio.to_thread()` in alerts loop
- **C6:** Make `admin_service_restart` Docker-aware
- **C7:** Unify version across all sources

### 🏗️ Architecture Refactoring
- Replace ~97 `print()` calls with structlog across 7 files
- Add `ThreadPoolExecutor(max_workers=4)` replacing 12 `threading.Thread` spawns
- Remove stale module-level credential snapshots, add lazy getters

### 🐳 CI/CD Hardening
- Add Python 3.13 matrix, bump coverage threshold 30→50
- Add paths-ignore, Trivy image scan, requirements-dev.txt
- Add anyio thread limiter config (100 threads)

### 🎨 PWA & A11y
- Remove `user-scalable=no` from viewport (WCAG compliance)
- Add `<noscript>` fallback, GZipMiddleware
- Fix manifest.json, add Cache-Control headers
- Add `/api/version` endpoint, `notificationclose` listener

### 📚 Documentation
- Add `CHANGELOG.md`, `SECURITY.md`, `CODEOWNERS`

### 📊 Stats
- Total changes: 5 PRs (#109, #111, #113, #116, #118)
- Files changed: 19
- Tests: 90/90 passing (was 85)
- Ruff: clean, Bandit: 0 issues

---

# Release v3.7.3

**Admin Panel Fix — Query Token Access Restored**

## What's New:
- Fix: restored `?t=` query-param support in `/admin` and `check_admin_token` (broken in v3.7.1)
- Migrated admin.html all API calls from `?t=${token}` to `X-Admin-Token` header for security
- Updated `telegram_bot_token_masked` reference in admin UI
- Added missing `Query` import

---

# Release v3.7.2

**CI Fixes & Dependency Updates**

## What's New:
- Fix CI: `tzdata==2026a` → `2026.2` (PyPI compatibility)
- Fix CI: synced `ruff==0.15.20` across local/CI (version mismatch caused format drift)
- Fix CI: restored `B404/B603/B607` bandit skips (safe subprocess usage)
- Bump: fastapi 0.135.3→0.139.0
- Bump: numpy 2.1.3→2.5.1
- Bump: uvicorn 0.34.0→0.50.2
- Bump: pydantic 2.13.0→2.13.4
- Bump: slowapi 0.1.1→0.1.10
- Bump: GitHub actions (checkout@v7, setup-python@v6, codeql-action@v4)
- Cleanup: 10 stale Dependabot branches removed

---

# Release v3.7.1

**Security Hardening, Rate Limiting, Supply-Chain Security & Refactoring**

## Что нового / What's New:

### 🔒 Security (Critical Fixes)
- **Webhook Secret Validation:** Telegram webhook now validates `X-Telegram-Bot-Api-Secret-Token` header (C1)
- **Path Traversal Fix:** `restore_backup` sanitizes filenames via `os.path.basename` + dot detection (C2)
- **Token Masking:** Admin API `/api/admin/data` masks bot token (`****XXXX`) instead of leaking it (C3)
- **Rate Limiting:** `slowapi` added — all endpoints rate-limited (webhook 60/min, admin 30/min, push 10/min, etc.) (C4)
- **Admin Token Security:** Removed query-parameter `?t=` — only `X-Admin-Token` header accepted; `secrets.compare_digest` used everywhere (H1, H2)
- **Pydantic Validation:** 8 endpoints migrated from `dict = Body()` to strict Pydantic models with regex patterns and bounds (H3)
- **SSRF Protection:** `fetch_custom` blocklist now uses `ipaddress` module, covers all private ranges (RFC 1918, cloud metadata `169.254.169.254`, IPv6) (H4)
- **Async HTTP:** Replaced blocking `requests.post` in webhook handler with `httpx.AsyncClient` (H5)

### 🐳 Docker & Supply-Chain Hardening
- `security_opt: no-new-privileges:true`, `cap_drop: [ALL]`, `pids_limit: 100` added to docker-compose
- `.dockerignore` fixed: `.venv/` excluded (342MB savings), expanded exclusions
- `bootstrap.py` TOCTOU race condition fixed (`os.O_CREAT | os.O_EXCL`)
- Trivy SARIF uploads to GitHub Security tab
- SLSA provenance + SBOM generation enabled
- `dependabot.yml` (pip + docker + github-actions, weekly)
- `.pre-commit-config.yaml` (ruff + pre-commit-hooks)
- CI: `pull_request` trigger, concurrency control, `ruff format --check`, `pytest --cov --cov-fail-under=30`
- Dockerfile: removed `dpkg --force-all --purge tar`, added OCI labels, reduced workers 4→2

### 🏗️ Refactoring
- `app/paths.py` — centralized data path constants
- `app/config_runtime.py` — cached config access with 30s TTL
- `app/reports/` package — extracted shared code from generate_*.py
- `app/_version.py` — single source of truth for version
- `db.py` — `init_db()` runs once (was called on every insert)
- Hardcoded personal Telegram ID removed from all fallbacks
- `get_air_raid_alert()` wrapped in `asyncio.to_thread`

### 📦 Dependencies
- `requests` 2.33.0 → 2.34.2
- `httpx` 0.27.0 → 0.28.1
- `pydantic-settings` 2.2.1 → 2.7.0
- `tzdata` 2025.1 → 2026a
- `slowapi` 0.1.1 added
- `matplotlib`, `numpy`, `pandas` pinned to exact versions

### 🧪 Tests
- 85 tests (+14 new): safety_net state machine, SSRF parser, path traversal
- Webhook secret 403 rejection test, rate limit test, edge cases

### 📊 Metrics
- Lines changed: +3,259 −2,577
- Files: 39 changed, 14 new
- Ruff: clean
- Bandit: Low-severity only (pre-existing subprocess with literal args)
