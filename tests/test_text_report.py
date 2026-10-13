import datetime
import json
import sys
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock

from app.reports import text as text_report

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def _make_mock_datetime(mock_now):
    class MockDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return mock_now

    return MockDatetime


def _get_sample_schedule_data():
    # 48 slots: 22 True (11h), 7 False (3.5h), 11 True (5.5h), 7 False (3.5h), 1 True (0.5h)
    today_slots = [True] * 22 + [False] * 7 + [True] * 11 + [False] * 7 + [True] * 1
    # Tomorrow slots: 28 True (14h), 7 False (3.5h), 11 True (5.5h), 2 False (1h)
    tomorrow_slots = [True] * 28 + [False] * 7 + [True] * 11 + [False] * 2

    return {
        "github": {
            "GPV36.1": {
                "2026-10-13": {"slots": today_slots, "status": "normal"},
                "2026-10-14": {"slots": tomorrow_slots, "status": "normal"},
            }
        },
        "yasno": {
            "GPV36.1": {
                "2026-10-13": {"slots": today_slots, "status": "normal"},
                "2026-10-14": {"slots": tomorrow_slots, "status": "normal"},
            }
        },
    }


def test_text_report_suppressed_before_morning_time():
    """Before 07:00 (e.g. 00:10 or 06:30), no Telegram messages should be sent."""
    mock_now = datetime.datetime(2026, 10, 13, 0, 10, 0, tzinfo=KYIV_TZ)
    data = _get_sample_schedule_data()

    with (
        patch("app.reports.text.datetime.datetime", _make_mock_datetime(mock_now)),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient") as mock_tg_cls,
        patch.object(sys, "argv", ["text.py"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    # TelegramClient shouldn't even be called to send messages
    mock_tg_cls.return_value.send_message.assert_not_called()
    mock_tg_cls.return_value.edit_message.assert_not_called()


def test_text_report_morning_at_07_00_sends_today_only():
    """At 07:00, morning schedule notification is sent for today only, without tomorrow."""
    mock_now = datetime.datetime(2026, 10, 13, 7, 0, 0, tzinfo=KYIV_TZ)
    data = _get_sample_schedule_data()
    saved_state = {}

    def fake_save_state(state):
        nonlocal saved_state
        saved_state = dict(state)

    mock_client = MagicMock()
    mock_client.send_message.return_value = 1001

    with (
        patch("app.reports.text.datetime.datetime", _make_mock_datetime(mock_now)),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("app.reports.text.get_report_state", return_value={}),
        patch("app.reports.text.save_report_state", side_effect=fake_save_state),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient", return_value=mock_client),
        patch.object(sys, "argv", ["text.py"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    assert mock_client.send_message.called
    sent_text = mock_client.send_message.call_args[0][0]
    # Today (13.10) must be present in the morning report
    assert "13.10" in sent_text
    # Tomorrow (14.10) must NOT be present in the morning report
    assert "14.10" not in sent_text
    assert saved_state["2026-10-13"]["morning_id"] == 1001


def test_text_report_evening_not_sent_at_20_00():
    """At 20:00, even if tomorrow's data exists, evening report is NOT sent yet (waits for 22:00)."""
    mock_now_morning = datetime.datetime(2026, 10, 13, 7, 0, 0, tzinfo=KYIV_TZ)
    data = _get_sample_schedule_data()
    mock_client = MagicMock()
    mock_client.send_message.return_value = 1001

    # First run at 07:00 to populate state
    captured_state = {}

    def fake_save(s):
        nonlocal captured_state
        captured_state = dict(s)

    with (
        patch(
            "app.reports.text.datetime.datetime", _make_mock_datetime(mock_now_morning)
        ),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("app.reports.text.get_report_state", return_value={}),
        patch("app.reports.text.save_report_state", side_effect=fake_save),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient", return_value=mock_client),
        patch.object(sys, "argv", ["text.py"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    # Now simulate 20:00 with morning state present
    mock_now_evening = datetime.datetime(2026, 10, 13, 20, 0, 0, tzinfo=KYIV_TZ)
    mock_client.reset_mock()

    with (
        patch(
            "app.reports.text.datetime.datetime", _make_mock_datetime(mock_now_evening)
        ),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("app.reports.text.get_report_state", return_value=captured_state),
        patch("app.reports.text.save_report_state"),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient", return_value=mock_client),
        patch.object(sys, "argv", ["text.py"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    # At 20:00, target_slot is still "morning", hash is unchanged, no evening message sent
    mock_client.send_message.assert_not_called()
    mock_client.edit_message.assert_not_called()


def test_text_report_evening_sent_at_22_00_without_morning():
    """At 22:00, evening report is sent for tomorrow only, without the morning schedule."""
    mock_now = datetime.datetime(2026, 10, 13, 22, 0, 0, tzinfo=KYIV_TZ)
    data = _get_sample_schedule_data()
    saved_state = {}

    def fake_save_state(state):
        nonlocal saved_state
        saved_state = dict(state)

    mock_client = MagicMock()
    mock_client.send_message.return_value = 1002

    existing_state = {
        "2026-10-13": {
            "morning_id": 1001,
            "morning_hash": "hash_morning",
        }
    }

    with (
        patch("app.reports.text.datetime.datetime", _make_mock_datetime(mock_now)),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("app.reports.text.get_report_state", return_value=existing_state),
        patch("app.reports.text.save_report_state", side_effect=fake_save_state),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient", return_value=mock_client),
        patch.object(sys, "argv", ["text.py"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    assert mock_client.send_message.called
    sent_text = mock_client.send_message.call_args[0][0]
    # Tomorrow (14.10) MUST be present in the evening report
    assert "14.10" in sent_text
    # Today (13.10) MUST NOT be present in the evening report ("без раннішнього")
    assert "13.10" not in sent_text
    assert saved_state["2026-10-13"]["evening_id"] == 1002


def test_text_report_force_new_bypasses_morning_time():
    """--force-new allows generating a report even before morning time window."""
    mock_now = datetime.datetime(2026, 10, 13, 5, 0, 0, tzinfo=KYIV_TZ)
    data = _get_sample_schedule_data()
    mock_client = MagicMock()
    mock_client.send_message.return_value = 1003

    with (
        patch("app.reports.text.datetime.datetime", _make_mock_datetime(mock_now)),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("app.reports.text.get_report_state", return_value={}),
        patch("app.reports.text.save_report_state"),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient", return_value=mock_client),
        patch.object(sys, "argv", ["text.py", "--force-new"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    assert mock_client.send_message.called


def test_text_report_edits_existing_message_on_schedule_change():
    """When schedule content changes, edit_message is called instead of send_message."""
    mock_now = datetime.datetime(2026, 10, 13, 12, 0, 0, tzinfo=KYIV_TZ)
    data = _get_sample_schedule_data()
    mock_client = MagicMock()
    mock_client.edit_message.return_value = 1001

    existing_state = {
        "2026-10-13": {
            "morning_id": 1001,
            "morning_hash": "stale_hash_from_previous_version",
        }
    }
    saved_state = {}

    def fake_save(s):
        nonlocal saved_state
        saved_state = dict(s)

    with (
        patch("app.reports.text.datetime.datetime", _make_mock_datetime(mock_now)),
        patch(
            "app.reports.text.load_config",
            return_value={"settings": {"groups": ["GPV36.1"]}},
        ),
        patch("app.reports.text.get_quiet_status", return_value="normal"),
        patch("app.reports.text.get_report_state", return_value=existing_state),
        patch("app.reports.text.save_report_state", side_effect=fake_save),
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
        patch("app.telegram_client.TelegramClient", return_value=mock_client),
        patch.object(sys, "argv", ["text.py"]),
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(
            data
        )
        text_report.main()

    assert mock_client.edit_message.called
    assert mock_client.edit_message.call_args[0][0] == 1001
    mock_client.send_message.assert_not_called()


def test_text_report_cleanup():
    """--cleanup removes stored telegram messages for today and yesterday."""
    mock_now = datetime.datetime(2026, 10, 13, 12, 0, 0, tzinfo=KYIV_TZ)
    existing_state = {
        "2026-10-13": {"morning_id": 1001, "evening_id": 1002},
        "2026-10-12": {"morning_id": 999, "evening_id": 1000},
    }
    saved_state = {}

    def fake_save(s):
        nonlocal saved_state
        saved_state = dict(s)

    with (
        patch("app.reports.text.datetime.datetime", _make_mock_datetime(mock_now)),
        patch("app.reports.text.get_report_state", return_value=existing_state),
        patch("app.reports.text.save_report_state", side_effect=fake_save),
        patch("app.reports.text.delete_telegram_message") as mock_del,
        patch.object(sys, "argv", ["text.py", "--cleanup"]),
    ):
        text_report.main()

    assert mock_del.call_count == 4
    mock_del.assert_any_call(1001)
    mock_del.assert_any_call(1002)
    mock_del.assert_any_call(999)
    mock_del.assert_any_call(1000)
    assert "morning_id" not in saved_state["2026-10-13"]
    assert "evening_id" not in saved_state["2026-10-13"]
