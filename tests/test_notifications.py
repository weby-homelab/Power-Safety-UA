import datetime
import time
from zoneinfo import ZoneInfo
from app.light_service import format_event_message

from unittest.mock import patch

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def test_format_event_message_very_soon_outage():
    # Light comes on at 19:29:50 (10 seconds before 19:30)
    event_time = datetime.datetime(2026, 3, 5, 19, 29, 50, tzinfo=KYIV_TZ).timestamp()
    prev_event_time = datetime.datetime(
        2026, 3, 5, 16, 40, 0, tzinfo=KYIV_TZ
    ).timestamp()

    # Mock next_info to simulate an event in 10 seconds
    mock_next_info = {"time_left_sec": 10, "interval": "19:30-22:00"}

    with patch(
        "app.light_service.get_next_scheduled_event", return_value=mock_next_info
    ):
        with patch("app.light_service.get_deviation_info", return_value=None):
            msg = format_event_message(True, event_time, prev_event_time)

            assert "❌ Вимкнення через ~ менше хвилини" in msg
            assert "🗓 (19:30-22:00)" in msg


def test_short_duration_formatting():
    from app.light_service import format_duration

    # Current behavior of format_duration for < 60s is "0 хв"
    assert format_duration(30) == "0 хв"
    assert format_duration(60) == "1 хв"


def test_format_duration_localization():
    from app.light_service import format_duration

    # English
    assert format_duration(30, lang="en") == "0m"
    assert format_duration(60, lang="en") == "1m"
    assert format_duration(3600, lang="en") == "1h"
    assert format_duration(3660, lang="en") == "1h 1m"
    assert format_duration(86400, lang="en") == "1d"
    assert format_duration(90000, lang="en") == "1d 1h"
    assert format_duration(95400, lang="en") == "1d 2h 30m"

    # Ukrainian (Default/UA)
    assert format_duration(30, lang="ua") == "0 хв"
    assert format_duration(60, lang="ua") == "1 хв"
    assert format_duration(3600, lang="ua") == "1 г"
    assert format_duration(3660, lang="ua") == "1 г 1 хв"
    assert format_duration(86400, lang="ua") == "1д"
    assert format_duration(90000, lang="ua") == "1д 1 год"
    assert format_duration(95400, lang="ua") == "1д 2 год 30 хв"


def test_get_schedule_context_localization():
    from app.light_service import get_schedule_context
    import json
    from unittest.mock import patch, mock_open

    # Test when schedule file exists but open fails (triggers exception and returns 'Помилка' / 'Error')
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert get_schedule_context(lang="ua") == (
                None,
                None,
                "Помилка",
                None,
                False,
            )
            assert get_schedule_context(lang="en") == (
                None,
                None,
                "Error",
                None,
                False,
            )

    # Test when schedule file exists but is empty (returns 'Невідомо' / 'Unknown')
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="{}")):
            assert get_schedule_context(lang="ua") == (
                None,
                None,
                "Невідомо",
                None,
                False,
            )
            assert get_schedule_context(lang="en") == (
                None,
                None,
                "Unknown",
                None,
                False,
            )

    # Test with emergency schedule when no slots
    schedule_emergency = {"yasno": {"G1": {"2026-03-18": {"status": "emergency"}}}}

    mock_now_dt = datetime.datetime(2026, 3, 18, 12, 0, 0, tzinfo=KYIV_TZ)
    with patch("app.light_service.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = mock_now_dt
        mock_datetime.timedelta = datetime.timedelta
        with patch("os.path.exists", return_value=True):
            with patch(
                "builtins.open", mock_open(read_data=json.dumps(schedule_emergency))
            ):
                assert get_schedule_context(lang="ua") == (
                    None,
                    None,
                    "⚠️ Екстрені відключення",
                    None,
                    True,
                )
                assert get_schedule_context(lang="en") == (
                    None,
                    None,
                    "⚠️ Emergency outages",
                    None,
                    True,
                )


def test_get_deviation_info_localization():
    from app.light_service import get_deviation_info
    import json
    from unittest.mock import patch, mock_open

    # 48 slots: True represents light, False represents outage.
    # At index 24 (12:00:00), we transition from True to False (outage starts)
    slots = [True] * 24 + [False] * 24
    schedule = {"yasno": {"G1": {"2026-03-18": {"slots": slots, "status": "normal"}}}}

    event_time_exact = datetime.datetime(
        2026, 3, 18, 12, 0, 0, tzinfo=KYIV_TZ
    ).timestamp()
    event_time_late = datetime.datetime(
        2026, 3, 18, 12, 15, 0, tzinfo=KYIV_TZ
    ).timestamp()
    event_time_early = datetime.datetime(
        2026, 3, 18, 11, 45, 0, tzinfo=KYIV_TZ
    ).timestamp()

    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=json.dumps(schedule))):
            # UA tests
            assert (
                get_deviation_info(event_time_exact, is_up=False, lang="ua")
                == "• Вимкнули точно за графіком"
            )
            assert (
                get_deviation_info(event_time_late, is_up=False, lang="ua")
                == "• Вимкнули пізніше на 15 хв"
            )
            assert (
                get_deviation_info(event_time_early, is_up=False, lang="ua")
                == "• Вимкнули раніше на 15 хв"
            )

            # EN tests
            assert (
                get_deviation_info(event_time_exact, is_up=False, lang="en")
                == "• Powered OFF strictly on schedule"
            )
            assert (
                get_deviation_info(event_time_late, is_up=False, lang="en")
                == "• Powered OFF later by 15m"
            )
            assert (
                get_deviation_info(event_time_early, is_up=False, lang="en")
                == "• Powered OFF earlier by 15m"
            )


@patch("app.light_service.subprocess.run")
@patch("app.light_service.os.open")
@patch("app.light_service.os.fdopen")
def test_trigger_daily_report_update(mock_fdopen, mock_open, mock_run):
    from app.light_service import trigger_daily_report_update
    import time

    # Mock os.open to succeed
    mock_open.return_value = 999

    # Trigger final report
    trigger_daily_report_update(is_final=True)

    # Wait for the thread to run
    time.sleep(0.1)

    # Assert subprocess.run was called with correct args
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "app.generate_daily_report" in args
    assert "--final" in args


class TestSafetyNetNotifications:
    """Test safety net notification edge cases."""

    def test_send_safety_net_admin_called(self):
        """send_safety_net_admin should POST to Telegram API."""
        from app.light_service import send_safety_net_admin

        with patch("app.light_service.get_telegram_token", return_value="test_token"):
            with patch("app.light_service.get_admin_chat_id", return_value="12345"):
                with patch("requests.post") as mock_post:
                    mock_post.return_value.status_code = 200
                    send_safety_net_admin(1234567890.0)
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "sendMessage" in call_args[0][0]
                    payload = call_args[1]["json"]
                    assert "SAFETY NET" in payload["text"]
                    assert "chat_id" in payload

    def test_send_safety_net_inline_keyboard(self):
        """Safety net message should have 2 rows of inline keyboard buttons."""
        from app.light_service import send_safety_net_admin

        with patch("app.light_service.get_telegram_token", return_value="test_token"):
            with patch("app.light_service.get_admin_chat_id", return_value="12345"):
                with patch("requests.post") as mock_post:
                    mock_post.return_value.status_code = 200
                    send_safety_net_admin(1234567890.0)
                    payload = mock_post.call_args[1]["json"]
                    keyboard = payload["reply_markup"]["inline_keyboard"]
                    assert len(keyboard) == 2
                    assert len(keyboard[0]) == 2
                    assert len(keyboard[1]) == 1

    def test_send_admin_confirmation_called(self):
        """send_admin_confirmation should POST to Telegram API."""
        from app.light_service import send_admin_confirmation

        with patch("app.light_service.get_telegram_token", return_value="test_token"):
            with patch("app.light_service.get_admin_chat_id", return_value="12345"):
                with patch("requests.post") as mock_post:
                    mock_post.return_value.status_code = 200
                    send_admin_confirmation(1234567890.0)
                    mock_post.assert_called_once()
                    call_args = mock_post.call_args
                    assert "sendMessage" in call_args[0][0]
                    payload = call_args[1]["json"]
                    assert "Інформаційний спокій" in payload["text"]


class TestFormatEventMessageEdgeCases:
    """Test edge cases in event message formatting."""

    def test_format_up_with_no_previous_event(self):
        """Up event with zero previous event time shows unknown duration."""
        now = time.time()
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(True, now, 0)
                    assert "невідомо" in msg

    def test_format_down_with_no_previous_event(self):
        """Down event with zero previous event time shows unknown duration."""
        now = time.time()
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(False, now, 0)
                    assert "невідомо" in msg

    def test_format_up_with_very_soon_interval(self):
        """Next event in less than 60 seconds shows 'менше хвилини'."""
        now = time.time()
        prev = now - 7200
        mock_next = {"time_left_sec": 30, "interval": "15:00-18:00"}
        with patch(
            "app.light_service.get_next_scheduled_event", return_value=mock_next
        ):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(True, now, prev)
                    assert "менше хвилини" in msg

    def test_format_up_with_no_schedule_at_all(self):
        """Up event from region without scheduled outages."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(True, now, prev)
                    assert "не плануються" in msg

    def test_format_down_with_no_schedule_at_all(self):
        """Down event from region without scheduled outages."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={"ui": {"text": {}}},
                ):
                    msg = format_event_message(False, now, prev)
                    assert "невідомий час" in msg

    def test_format_down_with_custom_text_overrides(self):
        """Custom text from config should be used in message."""
        now = time.time()
        prev = now - 3600
        with patch("app.light_service.get_next_scheduled_event", return_value=None):
            with patch("app.light_service.get_deviation_info", return_value=""):
                with patch(
                    "app.light_service.get_config",
                    return_value={
                        "ui": {
                            "text": {
                                "event_down": "CUSTOM_DOWN_TEXT {time}",
                                "dur_prefix_down": "CUSTOM_DUR_PREFIX",
                                "next_prefix_up": "CUSTOM_NEXT",
                            }
                        }
                    },
                ):
                    msg = format_event_message(False, now, prev)
                    assert "CUSTOM_DOWN_TEXT" in msg
                    assert "CUSTOM_DUR_PREFIX" in msg
                    assert "CUSTOM_NEXT" in msg
