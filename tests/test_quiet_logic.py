import pytest
import json
import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, mock_open

from app.light_service import check_quiet_mode_eligibility

KYIV_TZ = ZoneInfo("Europe/Kyiv")

def get_timestamp(date_str):
    return datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KYIV_TZ).timestamp()

@pytest.fixture
def mock_now():
    # 2026-03-18 12:00:00
    return get_timestamp("2026-03-18 12:00:00")

def test_eligible_quiet_mode(mock_now):
    """System is eligible: no past outages, no future planned outages."""
    event_log = [
        {"timestamp": mock_now - (50 * 3600), "event": "down", "date_str": "2026-03-16 10:00:00"},
        {"timestamp": mock_now - (49 * 3600), "event": "up", "date_str": "2026-03-16 11:00:00"}
    ]
    
    schedule = {
        "github": {
            "G1": {
                "2026-03-18": {"slots": [True] * 48},
                "2026-03-19": {"slots": [True] * 48}
            }
        }
    }
    
    def mocked_open(path, mode='r'):
        if "event_log.json" in path:
            return mock_open(read_data=json.dumps(event_log)).return_value
        if "last_schedules.json" in path:
            return mock_open(read_data=json.dumps(schedule)).return_value
        return mock_open().return_value

    with patch("time.time", return_value=mock_now), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=mocked_open):
        assert check_quiet_mode_eligibility() is True

def test_ineligible_past_outage(mock_now):
    """System is ineligible: outage happened 24h ago."""
    event_log = [
        {"timestamp": mock_now - (24 * 3600), "event": "down", "date_str": "2026-03-17 12:00:00"}
    ]
    
    schedule = {
        "github": {
            "G1": {
                "2026-03-18": {"slots": [True] * 48},
                "2026-03-19": {"slots": [True] * 48}
            }
        }
    }
    
    def mocked_open(path, mode='r'):
        if "event_log.json" in path:
            return mock_open(read_data=json.dumps(event_log)).return_value
        if "last_schedules.json" in path:
            return mock_open(read_data=json.dumps(schedule)).return_value
        return mock_open().return_value

    with patch("time.time", return_value=mock_now), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=mocked_open):
        assert check_quiet_mode_eligibility() is False

def test_ineligible_future_outage_today(mock_now):
    """System is ineligible: planned outage later today."""
    event_log = []
    
    # One false slot at 22:00
    today_slots = [True] * 48
    today_slots[44] = False
    
    schedule = {
        "github": {
            "G1": {
                "2026-03-18": {"slots": today_slots},
                "2026-03-19": {"slots": [True] * 48}
            }
        }
    }
    
    def mocked_open(path, mode='r'):
        if "event_log.json" in path:
            return mock_open(read_data=json.dumps(event_log)).return_value
        if "last_schedules.json" in path:
            return mock_open(read_data=json.dumps(schedule)).return_value
        return mock_open().return_value

    with patch("time.time", return_value=mock_now), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=mocked_open):
        assert check_quiet_mode_eligibility() is False

def test_ineligible_future_outage_tomorrow(mock_now):
    """System is ineligible: planned outage tomorrow."""
    event_log = []
    
    schedule = {
        "yasno": {
            "G1": {
                "2026-03-18": {"slots": [True] * 48},
                "2026-03-19": {"slots": [True, False] + [True]*46}
            }
        }
    }
    
    def mocked_open(path, mode='r'):
        if "event_log.json" in path:
            return mock_open(read_data=json.dumps(event_log)).return_value
        if "last_schedules.json" in path:
            return mock_open(read_data=json.dumps(schedule)).return_value
        return mock_open().return_value

    with patch("time.time", return_value=mock_now), \
         patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=mocked_open):
        assert check_quiet_mode_eligibility() is False

def test_missing_files(mock_now):
    """If files are missing, it should return False for safety."""
    with patch("os.path.exists", return_value=False):
        assert check_quiet_mode_eligibility() is False
