import time
import json
from unittest.mock import patch, mock_open
from app.light_service import (
    check_quiet_mode_eligibility,
    format_event_message,
)


class TestSafetyNetEligibility:
    """Test quiet mode eligibility logic — function reads from files, not a state dict."""

    def test_eligible_when_no_recent_outages_and_no_planned(self):
        """Quiet mode should be eligible when no recent events and no planned outages."""
        now = time.time()
        empty_logs = []
        schedule = {
            "github": {
                "G1": {
                    "2026-07-07": {"slots": [True] * 48},
                    "2026-07-08": {"slots": [True] * 48},
                }
            }
        }

        def mocked_open(path, mode="r"):
            if "event_log.json" in path:
                return mock_open(read_data=json.dumps(empty_logs)).return_value
            if "last_schedules.json" in path:
                return mock_open(read_data=json.dumps(schedule)).return_value
            return mock_open().return_value

        with patch("time.time", return_value=now):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", side_effect=mocked_open):
                    result = check_quiet_mode_eligibility()
                    assert result is True

    def test_not_eligible_when_recent_down_event(self):
        """Quiet mode should NOT be eligible when a down event occurred within 24h."""
        now = time.time()
        recent_logs = [
            {"timestamp": now - 3600, "event": "down", "date_str": "recent"}
        ]
        schedule = {
            "github": {
                "G1": {
                    "2026-07-07": {"slots": [True] * 48},
                    "2026-07-08": {"slots": [True] * 48},
                }
            }
        }

        def mocked_open(path, mode="r"):
            if "event_log.json" in path:
                return mock_open(read_data=json.dumps(recent_logs)).return_value
            if "last_schedules.json" in path:
                return mock_open(read_data=json.dumps(schedule)).return_value
            return mock_open().return_value

        with patch("time.time", return_value=now):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", side_effect=mocked_open):
                    result = check_quiet_mode_eligibility()
                    assert result is False

    def test_not_eligible_when_planned_outage_in_next_24h(self):
        """Quiet mode should NOT be eligible when outages are planned in the next 24h."""
        import datetime
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("Europe/Kyiv")
        midnight = datetime.datetime(2026, 7, 7, 0, 0, 0, tzinfo=tz)
        now = midnight.timestamp()
        empty_logs = []
        today_slots = [True] * 48
        today_slots[24] = False
        schedule = {
            "github": {
                "G1": {
                    "2026-07-07": {"slots": today_slots},
                    "2026-07-08": {"slots": [True] * 48},
                }
            }
        }

        def mocked_open(path, mode="r"):
            if "event_log.json" in path:
                return mock_open(read_data=json.dumps(empty_logs)).return_value
            if "last_schedules.json" in path:
                return mock_open(read_data=json.dumps(schedule)).return_value
            return mock_open().return_value

        with patch("time.time", return_value=now):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", side_effect=mocked_open):
                    result = check_quiet_mode_eligibility()
                    assert result is False

    def test_not_eligible_when_schedule_file_missing(self):
        """If schedule file is missing, should return False for safety."""
        now = time.time()
        empty_logs = []

        def mocked_open(path, mode="r"):
            if "event_log.json" in path:
                return mock_open(read_data=json.dumps(empty_logs)).return_value
            return mock_open().return_value

        with patch("time.time", return_value=now):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", side_effect=mocked_open):
                    result = check_quiet_mode_eligibility()
                    assert result is False

    def test_not_eligible_when_no_schedule_file_exists(self):
        """If schedule file does not exist, should return False."""
        now = time.time()
        empty_logs = []

        def mocked_open(path, mode="r"):
            if "event_log.json" in path:
                return mock_open(read_data=json.dumps(empty_logs)).return_value
            return mock_open().return_value

        with patch("time.time", return_value=now):
            with patch("os.path.exists", return_value=False):
                with patch("builtins.open", side_effect=mocked_open):
                    result = check_quiet_mode_eligibility()
                    assert result is False


class TestFormatEventMessage:
    """Test event message formatting."""

    def test_format_up_event(self):
        """Format up event should contain light-on related text."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(True, now, prev)
                    assert "Світло" in msg

    def test_format_down_event(self):
        """Format down event should contain light-off related text."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(False, now, prev)
                    assert "Світло" in msg

    def test_format_up_with_next_event(self):
        """Up event should include interval info when next_event is available."""
        now = time.time()
        prev = now - 3600
        mock_next = {"time_left_sec": 1800, "interval": "12:30-15:00"}
        with patch(
            "app.light_service.get_next_scheduled_event", return_value=mock_next
        ):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(True, now, prev)
                    assert "12:30-15:00" in msg

    def test_format_down_with_no_next_event(self):
        """Down event without schedule should include fallback text."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(False, now, prev)
                    assert "Очікуємо" in msg

    def test_format_up_with_deviation(self):
        """Up event with deviation info should include shift text."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch(
                "app.light_service.get_deviation_info",
                return_value="Увімкнули раніше на 15 хв",
            ):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(True, now, prev)
                    assert "раніше" in msg

    def test_format_down_with_exact_schedule_deviation(self):
        """Down event exactly on schedule."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch(
                "app.light_service.get_deviation_info",
                return_value="Вимкнули точно за графіком",
            ):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(False, now, prev)
                    assert "Точно за графіком" in msg
