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
