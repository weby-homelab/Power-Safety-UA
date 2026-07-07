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
    assert "📉 <b>План vs Факт:</b>" in caption
    assert "На цю хвилину" in caption
    assert "Світла 100% від плану" in caption

def test_build_report_caption_past_day():
    target_date = datetime.date(2026, 3, 4)
    now_time = datetime.datetime(2026, 3, 5, 12, 0, 0, tzinfo=KYIV_TZ)
    
    t_up = 24 * 3600 # 24 hours
    t_down = 0
    
    # 20.5 hours scheduled = 41 slots
    slots = [True] * 41 + [False] * 7
    
    caption, plan_up_sec_formatted, diff_hours, compliance_pct = build_report_caption(
        target_date, t_up, t_down, slots, now_time
    )
    
    assert "📊 <b>Звіт за 04.03.2026</b>" in caption
    assert "На кінець доби" in caption
    assert "Світла 117% від плану" in caption
