import datetime
from zoneinfo import ZoneInfo
from app.generate_daily_report import build_report_caption

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def test_build_report_caption_today():
    target_date = datetime.date(2026, 3, 5)
    now_time = datetime.datetime(2026, 3, 5, 12, 0, 0, tzinfo=KYIV_TZ)

    # Simulate 12 hours of light (43200 seconds) and 0 down
    t_up = 43200
    t_down = 0

    # Simulate slots: 24 slots of True (12 hours) and 24 slots of False
    slots = [True] * 24 + [False] * 24

    caption, plan_up_sec_formatted, diff_hours, compliance_pct = build_report_caption(
        target_date, t_up, t_down, slots, now_time
    )

    assert "📊 <b>Звіт за 05.03.2026</b>" in caption
    assert "💡 Світло було: 12 г" in caption
    assert "⚡ Світла не було: 0 хв" in caption
    assert "🗓️ <b>План vs факт</b>" in caption
    assert "План на добу: 12 г" in caption
    assert "Факт: 12 г" in caption
    assert "Виконання плану: 100%" in caption
    assert "Оновлено: 12:00" in caption
    assert "👉" not in caption
    assert "🕐" not in caption


def test_build_report_caption_past_day():
    target_date = datetime.date(2026, 3, 4)
    now_time = datetime.datetime(2026, 3, 5, 12, 0, 0, tzinfo=KYIV_TZ)

    t_up = 24 * 3600  # 24 hours
    t_down = 0

    # 20.5 hours scheduled = 41 slots
    slots = [True] * 41 + [False] * 7

    caption, plan_up_sec_formatted, diff_hours, compliance_pct = build_report_caption(
        target_date, t_up, t_down, slots, now_time
    )

    assert "📊 <b>Звіт за 04.03.2026</b>" in caption
    assert "💡 Світло було: 24 г" in caption
    assert "⚡ Світла не було: 0 хв" in caption
    assert "🗓️ <b>План vs факт</b>" in caption
    assert "План на добу: 20 г 30 хв" in caption
    assert "Факт: 24 г" in caption
    assert "Виконання плану: 117%" in caption
    assert "Оновлено: 12:00" in caption
    assert "👉" not in caption
    assert "🕐" not in caption


def test_build_report_caption_with_alerts_and_aqi(tmp_path):
    from unittest.mock import patch
    import json

    target_date = datetime.date(2026, 10, 9)
    now_time = datetime.datetime(2026, 10, 9, 20, 0, 0, tzinfo=KYIV_TZ)

    # 1. Mock air raid log with yellow and red alerts
    air_raid_log = [
        {
            "timestamp": datetime.datetime(
                2026, 10, 9, 2, 0, tzinfo=KYIV_TZ
            ).timestamp(),
            "event": "active",
            "alert_type": "yellow",
        },
        {
            "timestamp": datetime.datetime(
                2026, 10, 9, 3, 0, tzinfo=KYIV_TZ
            ).timestamp(),
            "event": "clear",
            "alert_type": "yellow",
        },
        {
            "timestamp": datetime.datetime(
                2026, 10, 9, 4, 0, tzinfo=KYIV_TZ
            ).timestamp(),
            "event": "active",
            "alert_type": "red",
        },
        {
            "timestamp": datetime.datetime(
                2026, 10, 9, 7, 15, tzinfo=KYIV_TZ
            ).timestamp(),
            "event": "clear",
            "alert_type": "red",
        },
    ]
    with open(tmp_path / "air_raid_log.json", "w") as f:
        json.dump(air_raid_log, f)

    # 2. Mock metrics history with AQI
    t_start = datetime.datetime(2026, 10, 9, 0, 0, tzinfo=KYIV_TZ).timestamp()
    metrics = [
        {"timestamp": t_start + i * 600, "aqi": 35 if i < 30 else 65}
        for i in range(60)  # 10 hours of data: 5h Good, 5h Moderate
    ]
    with open(tmp_path / "metrics_history.json", "w") as f:
        json.dump(metrics, f)

    with patch("app.reports.daily.DATA_DIR", str(tmp_path)):
        caption, *_ = build_report_caption(
            target_date, 10 * 3600, 2 * 3600, [True] * 48, now_time
        )

    assert "🚨 Тривоги без подвійного рахунку: 4 г 15 хв" in caption
    assert "Жовтий 1 г (4.2%)" in caption
    assert "Червоний 3 г 15 хв (13.5%)" in caption
    assert "🌫️ AQI:" in caption
    assert "Добре 5 г (20.8%)" in caption
    assert "Помірне 5 г (20.8%)" in caption
