# Implementation Plan: Air-raid alert type visualization and v3.9.11 release

## Overview

Extend the existing air-raid history pipeline with the alert-level data already exposed by Alerts.in.ua: yellow warning-level records and red immediate-danger records are preserved as separate intervals in daily and weekly reports. Expose the same normalized level in the live dashboard card while keeping a red-level fallback for legacy official-alert records.

## Architecture decisions

- Use normalized alert types `yellow` and `red`; red takes precedence for the effective live card when both are active.
- Read validated alert records from `https://api.alerts.in.ua/v3/etryvoga/alerts/active.json`, classify by the provider's level/message fields, and keep a conservative red fallback for the existing JAAM official-alert endpoint.
- Store `alert_type` on new history events and parse legacy events as `red` to preserve existing official-alert semantics.
- Keep chart rendering in the shared report-history layer so daily and weekly charts use the same interval contract and colors.

## Task list

1. Add failing tests for alert normalization, typed history intervals, chart colors, and dashboard card text/classes.
2. Implement typed API responses, transition logging, shared interval parsing, and daily/weekly rendering.
3. Update version/changelog/release notes for `v3.9.11` and dependency fixes required by the release gate.
4. Run focused tests, full tests, Ruff, Bandit, dependency audit, and a rendered-chart/API smoke test.
5. Review and publish through a feature PR; merge only after exact CI/read-back checks.
6. Process existing PRs and Dependabot alerts only after re-reading their exact current state and verifying the resulting default-branch state.
7. Deploy the verified release to staging LXC200, then production HTZNR, with health/log/version checks.

## Acceptance criteria

- A yellow-level alert renders yellow and is labeled as a warning-level alert.
- A red-level alert renders red and is labeled as an immediate-danger alert.
- If both are active, the live card identifies the red level while historical bars preserve both typed intervals.
- Daily and weekly chart legends identify both alert colors; the levels use the full-height alert strip without artificial internal lanes or gaps.
- Existing legacy alert log records remain readable.
- `v3.9.11` is the version reported by the application, tag, GitHub release, and deployed services.
- All tests, lint/SAST/dependency gates, release read-back, and both deployment smoke checks pass.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Existing logs have no type | Treat legacy `active`/`clear` pairs as city/red and test the fallback. |
| Yellow-to-red transitions overlap | Track level-specific active/clear events independently and use red precedence only for the live card. |
| Dependency PRs change runtime behavior | Inspect each diff, run the full suite, merge only verified updates, and read back alert state. |
| Production deployment serves a stale image | Pin/verify the release version, pull explicitly, inspect image/container metadata and `/health/live`. |
