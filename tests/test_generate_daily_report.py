import pytest
import datetime
from zoneinfo import ZoneInfo
import os
import json
from unittest.mock import patch, mock_open

from app.generate_daily_report import (
    load_events,
    load_schedule_slots,
    get_intervals_for_date,
    get_schedule_intervals,
    format_duration,
    get_last_report_id,
    save_report_id,
    generate_chart,
)

KYIV_TZ = ZoneInfo("Europe/Kyiv")

def test_format_duration():
    assert format_duration(60) == "1 хв"
    assert format_duration(3600) == "1 г"
    assert format_duration(3660) == "1 г 1 хв"
    assert format_duration(30) == "0 хв"

@patch("os.path.exists")
def test_load_events_no_file(mock_exists):
    mock_exists.return_value = False
    assert load_events() == []

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data='[{"event": "up"}]')
def test_load_events_with_file(mock_file, mock_exists):
    mock_exists.return_value = True
    assert load_events() == [{"event": "up"}]

@patch("os.path.exists")
def test_load_schedule_slots_no_files(mock_exists):
    mock_exists.return_value = False
    date = datetime.date(2026, 4, 6)
    assert load_schedule_slots(date) == [True] * 48

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open)
@patch("app.light_service.get_config")
def test_load_schedule_slots_with_schedule(mock_get_config, mock_file, mock_exists):
    mock_exists.return_value = True
    mock_get_config.return_value = {"advanced": {"data_sources": {"priority": "yasno"}}}
    
    mock_schedule = {
        "yasno": {
            "G1": {
                "2026-04-06": {"slots": [True] * 48}
            }
        }
    }
    mock_file.return_value.read.return_value = json.dumps(mock_schedule)
    
    date = datetime.date(2026, 4, 6)
    slots = load_schedule_slots(date)
    assert slots == [True] * 48

def test_get_intervals_for_date():
    date = datetime.date(2026, 4, 6)
    events = [
        {"timestamp": datetime.datetime(2026, 4, 6, 10, 0, tzinfo=KYIV_TZ).timestamp(), "event": "down"},
        {"timestamp": datetime.datetime(2026, 4, 6, 12, 0, tzinfo=KYIV_TZ).timestamp(), "event": "up"},
    ]
    with patch("app.generate_daily_report.get_now") as mock_get_now:
        mock_get_now.return_value = datetime.datetime(2026, 4, 6, 14, 0, tzinfo=KYIV_TZ)
        intervals = get_intervals_for_date(date, events)
        assert len(intervals) == 3
        assert intervals[0][2] == "unknown" # 00:00 to 10:00
        assert intervals[1][2] == "down"    # 10:00 to 12:00
        assert intervals[2][2] == "up"      # 12:00 to 14:00 (now)

def test_get_schedule_intervals():
    date = datetime.date(2026, 4, 6)
    slots = [True] * 48
    slots[0] = False # 00:00 to 00:30 is off
    
    intervals = get_schedule_intervals(date, slots)
    assert len(intervals) == 2
    assert intervals[0][1] == 0.5 # 0.5 hours
    assert intervals[0][2] is False
    assert intervals[1][1] == 23.5
    assert intervals[1][2] is True

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data='{"2026-04-06": 1234}')
def test_get_last_report_id(mock_file, mock_exists):
    mock_exists.return_value = True
    date = datetime.date(2026, 4, 6)
    assert get_last_report_id(date) == 1234

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data='{}')
def test_save_report_id(mock_file, mock_exists):
    mock_exists.return_value = True
    date = datetime.date(2026, 4, 6)
    save_report_id(1234, date)
    
    # Check if write was called
    mock_file().write.assert_called()

@patch("matplotlib.pyplot.savefig")
def test_generate_chart(mock_savefig):
    date = datetime.date(2026, 4, 6)
    
    day_start = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    intervals = [
        (day_start, day_start + datetime.timedelta(hours=10), "up"),
        (day_start + datetime.timedelta(hours=10), day_start + datetime.timedelta(hours=12), "down"),
        (day_start + datetime.timedelta(hours=12), day_start + datetime.timedelta(hours=24), "up"),
    ]
    
    schedule_intervals = [
        (day_start, 24.0, True)
    ]
    
    filename, t_up, t_down = generate_chart(date, intervals, schedule_intervals, [], theme='dark')
    assert "report_2026-04-06.png" in filename
    assert t_up == 22 * 3600
    assert t_down == 2 * 3600
    mock_savefig.assert_called_once()

@patch("matplotlib.pyplot.savefig")
def test_generate_chart_en(mock_savefig):
    date = datetime.date(2026, 4, 6)
    
    day_start = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    intervals = [
        (day_start, day_start + datetime.timedelta(hours=10), "up"),
    ]
    
    schedule_intervals = [
        (day_start, 24.0, True)
    ]
    
    filename, t_up, t_down = generate_chart(date, intervals, schedule_intervals, [], theme='dark', lang='en')
    assert "report_2026-04-06_en.png" in filename
    mock_savefig.assert_called_once()

@patch("requests.get")
@patch("matplotlib.pyplot.savefig")
def test_generate_chart_filters_future_aqi(mock_savefig, mock_get):
    date = datetime.date(2026, 4, 6)
    day_start = datetime.datetime.combine(date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    
    # Mock Open-Meteo API response
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "hourly": {
            "pm2_5": [10.0] * 24
        }
    }
    
    # Mock get_now to 12:00 in Kyiv timezone
    with patch("app.generate_daily_report.get_now") as mock_get_now:
        mock_get_now.return_value = datetime.datetime(2026, 4, 6, 12, 0, tzinfo=KYIV_TZ)
        filename, t_up, t_down = generate_chart(date, [], [], [], theme='dark')
        assert "report_2026-04-06.png" in filename
        mock_savefig.assert_called()

