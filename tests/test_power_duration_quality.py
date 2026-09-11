from unittest.mock import patch
from app.light_service import format_event_message


def test_power_duration_normal_forward_interval():
    # 2 hours between outage and restoration
    t_prev = 1775450000.0
    t_event = 1775457200.0  # +7200s (2 hours)
    msg = format_event_message(True, t_event, t_prev)
    assert "2 г" in msg
    assert "невідомо" not in msg


def test_power_duration_clock_rollback_negative_interval():
    # prev_event_time > event_time (clock rollback or corrupted state)
    t_prev = 1775457200.0
    t_event = 1775450000.0
    with patch("app.light_service.logger.warning") as mock_warn:
        msg = format_event_message(True, t_event, t_prev)
        assert "невідомо" in msg
        mock_warn.assert_called_once()
        call_kwargs = mock_warn.call_args[1]
        assert call_kwargs["event_time"] == t_event
        assert call_kwargs["prev_event_time"] == t_prev
        assert call_kwargs["diff_sec"] < 0


def test_power_duration_missing_previous_event():
    # prev_event_time is 0 or None
    msg_zero = format_event_message(False, 1775450000.0, 0.0)
    assert "невідомо" in msg_zero

    msg_none = format_event_message(False, 1775450000.0, None)
    assert "невідомо" in msg_none


def test_power_duration_strictly_non_negative():
    # Ensure zero difference produces 0m or known valid non-negative string
    t_event = 1775450000.0
    t_prev = 1775450000.0
    msg = format_event_message(True, t_event, t_prev)
    assert "невідомо" not in msg
    assert "-" not in msg
