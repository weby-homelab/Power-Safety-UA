# Design: Chart Layout and Air Quality Filtering Optimization

**Date:** 2026-06-03
**Target Version:** `v3.5.2`

## 1. Objectives
- Reduce the height of the graphical daily report bars by 50% (from `2.0` to `1.0`).
- Ensure the narrower bars are visually centered and y-ticks align perfectly with them.
- Restrict air quality (AQI) data visualization to only show past and current hours (skip future predictions).
- Cleanly release version `v3.5.2` on GitHub/Docker Hub, deploy to HTZNR and LXC200, and verify.

## 2. Proposed Changes

### A. Daily Graphic Chart Height & Y-Position Adjustments
In [app/generate_daily_report.py](file:///root/geminicli/projects/flash-monitor-kyiv/app/generate_daily_report.py):
- Update heights of the four bars to `1.0`:
  - `aqi_h = 1.0`
  - `alert_h = 1.0`
  - `sched_h = 1.0`
  - `act_h = 1.0`
- Adjust starting Y-positions to keep them centered relative to the original `2.0` layout space:
  - `aqi_y = 9.5`
  - `alert_y = 11.5`
  - `sched_y = 13.5`
  - `act_y = 15.5`
- Keep `ax.vlines` height limits from `9.0` to `17.0` to display full-height hourly divider lines.
- Keep y-ticks `ax.set_yticks` centered as before, since center values like `aqi_y + aqi_h/2` evaluates to `10.0` (same as `9.0 + 2.0/2`).

### B. Air Quality Hour Filtering
In [app/generate_daily_report.py](file:///root/geminicli/projects/flash-monitor-kyiv/app/generate_daily_report.py):
- Fetch the hourly AQI forecast as before.
- When iterating over the hourly data, calculate `start_t = datetime.datetime.combine(target_date, datetime.time(i, 0)).replace(tzinfo=KYIV_TZ)`.
- Skip appending the interval if `start_t > now`, where `now = datetime.datetime.now(KYIV_TZ)`.
- For the fallback case (when the API is down or unavailable), if the date is today, limit the fallback duration to `min(day_end, now)`. If it is a future day, do not output any fallback interval.

### C. Version Updates
Update files to reference `3.5.2`:
- `VERSION`
- `release_notes.md`
- `docker-compose.yml`
- `README.md`
- `README_ENG.md`

## 3. Testing and Verification
- Run local unit tests in the container or host to verify functionality:
  ```bash
  python3 -m pytest tests/
  ```
- Generate mock reports and review their output graphics to ensure bars are centered and only past/current hours of AQI are shown.

## 4. Deployment Pipeline
- Create a new branch `feature/v3.5.2-chart-narrowing`.
- Commit changes with GPG signed tag `v3.5.2`.
- Open a GitHub pull request and merge to `main`.
- Deploy via `/root/geminicli/deploy_all.py`.
- Verify containers on HTZNR and LXC200.
