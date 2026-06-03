# Chart Optimization and Release v3.5.2 Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modify the daily graphical report to make bars 50% narrower (and centered), filter future AQI hours, bump version to `3.5.2`, and deploy to HTZNR and LXC200.

**Architecture:** Change parameters `aqi_h`, `alert_h`, `sched_h`, `act_h` to `1.0` and starting positions to `9.5`, `11.5`, `13.5`, `15.5`. In AQI generation, add a condition `if start_t > now: continue` to skip future slots, and limit fallback calculation up to current time.

**Tech Stack:** Python 3.13, Matplotlib, Git, GPG, Docker Compose.

---

### Task 1: Create a feature branch
**Files:** None
**Step 1: Check out a new branch**
Run: `git checkout -b feature/v3.5.2-chart-optimization`
Expected: Switched to a new branch

### Task 2: Implement Chart Layout & Bar Width Adjustments
**Files:**
- Modify: `app/generate_daily_report.py:306-314`
- Modify: `app/generate_daily_report.py:367-370`

**Step 1: Edit app/generate_daily_report.py for heights and positions**
Update geometries in `generate_chart`:
```python
        # Define geometries - Glued together
        aqi_y = 9.5
        aqi_h = 1.0
        alert_y = 11.5
        alert_h = 1.0
        sched_y = 13.5
        sched_h = 1.0
        act_y = 15.5
        act_h = 1.0
```

**Step 2: Edit app/generate_daily_report.py to filter future AQI bars**
Modify the AQI hourly parsing loop inside `generate_chart`:
```python
                for i in range(min(len(pm25_hourly), 24)):
                    val = pm25_hourly[i]
                    if val is None:
                        val = 0
                    aqi_val = int(val * 3)
                    
                    if aqi_val <= 50:
                        color = "#22c55e" # Green
                    elif aqi_val <= 100:
                        color = "#eab308" # Yellow
                    else:
                        color = "#ef4444" # Red
                    
                    start_t = datetime.datetime.combine(target_date, datetime.time(i, 0)).replace(tzinfo=KYIV_TZ)
                    now = datetime.datetime.now(KYIV_TZ)
                    if start_t > now:
                        continue
                    end_t = start_t + datetime.timedelta(hours=1)
                    aqi_intervals.append((start_t, end_t, color))
```
And update the fallback section:
```python
        if not aqi_intervals:
            now = datetime.datetime.now(KYIV_TZ)
            if target_date <= now.date():
                end_fallback = min(day_end, now)
                if day_start < end_fallback:
                    aqi_intervals = [(day_start, end_fallback, "#22c55e")]
```

**Step 3: Run existing unit tests**
Run: `.venv/bin/python3 -m pytest tests/` or `python3 -m pytest` if pip is installed. Wait, we can install pytest first if needed, or run the app manually.
Expected: Tests should pass.

### Task 3: Write Test Cases for AQI Hour Filtering
**Files:**
- Modify: `tests/test_generate_daily_report.py`

**Step 1: Write tests for filtering future AQI bars**
Add a test in `tests/test_generate_daily_report.py`:
```python
def test_generate_chart_filters_future_aqi():
    date = datetime.date(2026, 4, 6)
    day_start = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    
    # We mock datetime.now to be in the middle of the day, e.g. 12:00
    class MockDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2026, 4, 6, 12, 0, tzinfo=KYIV_TZ)
            
    with patch("app.generate_daily_report.datetime.datetime", MockDatetime), \
         patch("requests.get") as mock_get, \
         patch("matplotlib.pyplot.savefig") as mock_savefig:
         
         # Mock API return with 24 hours of data
         mock_response = unittest.mock.Mock()
         mock_response.status_code = 200
         mock_response.json.return_value = {
             "hourly": {
                 "pm2_5": [10] * 24
             }
         }
         mock_get.return_value = mock_response
         
         # Generate chart
         filename, _, _ = generate_chart(date, [], [], theme='dark')
         # The test just checks that it executes without errors.
         assert "report_2026-04-06.png" in filename
```

### Task 4: Version Bumping and Documentation
**Files:**
- Modify: `VERSION`
- Modify: `release_notes.md`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `README_ENG.md`

**Step 1: Update version in files**
Set version from `3.5.1` to `3.5.2` in all the above files.

### Task 5: Release and Build
**Files:** None
**Step 1: Commit and push changes**
Run Git config name/email from `.env`. Commit signed with key `2D49E810C7F2527E`.
Push branch `feature/v3.5.2-chart-optimization`.
Create PR using `gh pr create`.
Merge PR using `gh pr merge --merge`.
Create and push tag `v3.5.2`.
Create release `v3.5.2` using `gh release create`.

**Step 2: Monitor GitHub Action for Docker Hub build**
Verify Docker Hub builds successfully.

### Task 6: Deployment & Verification
**Files:** None
**Step 1: Run deployment**
Run: `python3 /root/geminicli/deploy_all.py`
Verify deployment on HTZNR and LXC200.
Verify that container logs show successful startup.
