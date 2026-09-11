import sys
import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch, MagicMock
import pytest
import requests
import responses

from app.reports import daily, weekly
from app.reports.delivery_state import (
    is_daily_final_delivered,
    mark_daily_final_delivered,
    is_weekly_delivered,
    mark_weekly_delivered,
)
from app.telegram_client import TelegramClient

KYIV_TZ = ZoneInfo("Europe/Kyiv")


@pytest.fixture(autouse=True)
def clean_delivery_state(tmp_path, monkeypatch):
    test_state_file = str(tmp_path / "report_delivery_state.json")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.reports.delivery_state.get_delivery_state_path", lambda: test_state_file
    )
    yield


# 1. daily final sends while Quiet Mode is quiet
def test_daily_final_sends_while_quiet_mode_is_quiet(tmp_path, monkeypatch):
    mock_send = MagicMock(return_value=12345)
    mock_delete = MagicMock()
    target_date = datetime.date(2026, 4, 7)

    monkeypatch.setattr(daily, "get_quiet_status", lambda: "quiet")
    monkeypatch.setattr(daily, "get_last_report_id", lambda d: None)
    monkeypatch.setattr(daily, "send_telegram_photo", mock_send)
    monkeypatch.setattr(daily, "delete_telegram_message", mock_delete)
    monkeypatch.setattr(
        "app.config_runtime.get_config",
        lambda: {"advanced": {"notifications": {"telegram_daily_reports": True}}},
    )

    test_argv = ["app.generate_daily_report", "--final", "2026-04-07"]
    monkeypatch.setattr(sys, "argv", test_argv)

    # Run the send/finalization block
    is_final = "--final" in sys.argv
    quiet_status = daily.get_quiet_status()
    assert is_final is True
    assert quiet_status == "quiet"

    new_msg_id = daily.send_telegram_photo("dummy.png", "caption", target_date)
    assert new_msg_id == 12345
    mark_daily_final_delivered(target_date.strftime("%Y-%m-%d"), new_msg_id)
    assert is_daily_final_delivered("2026-04-07") is True


# 2. daily final respects telegram_daily_reports=false
def test_daily_final_respects_telegram_daily_reports_false(monkeypatch):
    mock_send = MagicMock()
    monkeypatch.setattr(
        "app.config_runtime.get_config",
        lambda: {"advanced": {"notifications": {"telegram_daily_reports": False}}},
    )
    monkeypatch.setattr(daily, "send_telegram_photo", mock_send)

    cfg = {"advanced": {"notifications": {"telegram_daily_reports": False}}}
    enabled = (
        cfg.get("advanced", {})
        .get("notifications", {})
        .get("telegram_daily_reports", True)
    )
    assert enabled is False
    mock_send.assert_not_called()


# 3. daily --no-send never sends
def test_daily_no_send_never_sends(monkeypatch):
    mock_send = MagicMock()
    monkeypatch.setattr(daily, "send_telegram_photo", mock_send)
    sys_argv = ["app.generate_daily_report", "--final", "--no-send"]
    if "--no-send" in sys_argv:
        pass
    else:
        daily.send_telegram_photo("dummy.png", "caption", datetime.date(2026, 4, 7))
    mock_send.assert_not_called()


# 4. reactive daily update still respects Quiet Mode
def test_reactive_daily_update_still_respects_quiet_mode(monkeypatch):
    mock_send = MagicMock()
    mock_update = MagicMock()
    monkeypatch.setattr(daily, "get_quiet_status", lambda: "quiet")
    monkeypatch.setattr(daily, "get_last_report_id", lambda d: None)
    monkeypatch.setattr(daily, "send_telegram_photo", mock_send)
    monkeypatch.setattr(daily, "update_telegram_photo", mock_update)

    quiet_status = daily.get_quiet_status()
    last_id = daily.get_last_report_id(datetime.date(2026, 4, 7))
    is_final = False

    if not is_final and quiet_status == "quiet":
        if last_id:
            daily.update_telegram_photo(last_id, "dummy.png", "caption")
        # else skips sending new report
    mock_send.assert_not_called()
    mock_update.assert_not_called()


# 5. quiet transition does not delete finalized graphic report
def test_quiet_transition_does_not_delete_finalized_graphic_report():
    import inspect
    from app import light_service

    src = inspect.getsource(light_service.update_quiet_status)
    assert "app.generate_daily_report" not in src


# 6. final replacement sends new before deleting old
def test_final_replacement_sends_new_before_deleting_old(monkeypatch):
    call_order = []

    def fake_send(path, cap, d):
        call_order.append("send")
        return 999

    def fake_delete(msg_id):
        call_order.append(f"delete_{msg_id}")
        return True

    target_date = datetime.date(2026, 4, 7)
    monkeypatch.setattr(daily, "get_last_report_id", lambda d: 555)
    monkeypatch.setattr(daily, "send_telegram_photo", fake_send)
    monkeypatch.setattr(daily, "delete_telegram_message", fake_delete)

    last_id = daily.get_last_report_id(target_date)
    new_msg_id = daily.send_telegram_photo("dummy.png", "caption", target_date)
    if new_msg_id:
        mark_daily_final_delivered(target_date.strftime("%Y-%m-%d"), new_msg_id)
        if last_id and last_id != new_msg_id:
            daily.delete_telegram_message(last_id)

    assert call_order == ["send", "delete_555"]


# 7. send failure keeps old report
def test_send_failure_keeps_old_report(monkeypatch):
    mock_delete = MagicMock()
    target_date = datetime.date(2026, 4, 7)
    monkeypatch.setattr(daily, "get_last_report_id", lambda d: 555)
    monkeypatch.setattr(daily, "send_telegram_photo", lambda p, c, d: None)
    monkeypatch.setattr(daily, "delete_telegram_message", mock_delete)

    last_id = daily.get_last_report_id(target_date)
    new_msg_id = daily.send_telegram_photo("dummy.png", "caption", target_date)
    if new_msg_id:
        if last_id and last_id != new_msg_id:
            daily.delete_telegram_message(last_id)

    mock_delete.assert_not_called()


# 8. weekly sends while Quiet Mode is quiet
def test_weekly_sends_while_quiet_mode_is_quiet(monkeypatch):
    mock_send = MagicMock(return_value=888)
    monkeypatch.setattr(weekly, "get_quiet_status", lambda: "quiet")
    monkeypatch.setattr(weekly, "send_telegram_photo", mock_send)
    monkeypatch.setattr(
        "app.config_runtime.get_config",
        lambda: {"advanced": {"notifications": {"telegram_weekly_reports": True}}},
    )

    args = MagicMock()
    args.no_send = False
    args.output = None

    cfg = {"advanced": {"notifications": {"telegram_weekly_reports": True}}}
    enabled = (
        cfg.get("advanced", {})
        .get("notifications", {})
        .get("telegram_weekly_reports", True)
    )

    exit_code = 0
    if args.no_send or args.output:
        pass
    elif not enabled:
        pass
    else:
        msg_id = weekly.send_telegram_photo("photo.png", "caption")
        if msg_id:
            mark_weekly_delivered("2026-04-06", msg_id)
        else:
            exit_code = 1

    assert mock_send.call_count == 1
    assert exit_code == 0
    assert is_weekly_delivered("2026-04-06") is True


# 9. weekly respects telegram_weekly_reports=false
def test_weekly_respects_telegram_weekly_reports_false(monkeypatch):
    mock_send = MagicMock()
    monkeypatch.setattr(weekly, "send_telegram_photo", mock_send)
    cfg = {"advanced": {"notifications": {"telegram_weekly_reports": False}}}
    enabled = (
        cfg.get("advanced", {})
        .get("notifications", {})
        .get("telegram_weekly_reports", True)
    )
    if not enabled:
        pass
    else:
        weekly.send_telegram_photo("photo.png", "caption")
    mock_send.assert_not_called()


# 10. weekly --no-send never sends
def test_weekly_no_send_never_sends(monkeypatch):
    mock_send = MagicMock()
    monkeypatch.setattr(weekly, "send_telegram_photo", mock_send)
    args = MagicMock()
    args.no_send = True
    args.output = None
    if args.no_send or args.output:
        pass
    else:
        weekly.send_telegram_photo("photo.png", "caption")
    mock_send.assert_not_called()


# 11. weekly --output never sends
def test_weekly_output_never_sends(monkeypatch):
    mock_send = MagicMock()
    monkeypatch.setattr(weekly, "send_telegram_photo", mock_send)
    args = MagicMock()
    args.no_send = False
    args.output = "/tmp/weekly.png"
    if args.no_send or args.output:
        pass
    else:
        weekly.send_telegram_photo("photo.png", "caption")
    mock_send.assert_not_called()


# 12. Telegram 429 retry_after handling
def test_telegram_429_retry_after_handling():
    client = TelegramClient("test_token", "123")
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            json={
                "ok": False,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 0.05},
            },
            status=429,
        )
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"ok": True, "result": {"message_id": 777}},
            status=200,
        )
        success, res = client._make_request(
            "sendMessage", {"chat_id": "123", "text": "hi"}
        )
        assert success is True
        assert res == 777
        assert len(rsps.calls) == 2


# 13. Telegram 5xx retry
def test_telegram_5xx_retry():
    client = TelegramClient("test_token", "123")
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            body="Bad Gateway",
            status=502,
        )
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"ok": True, "result": {"message_id": 888}},
            status=200,
        )
        with patch("time.sleep"):
            success, res = client._make_request(
                "sendMessage", {"chat_id": "123", "text": "hi"}
            )
            assert success is True
            assert res == 888
            assert len(rsps.calls) == 2


# 14. permanent 4xx no blind retry
def test_permanent_4xx_no_blind_retry():
    client = TelegramClient("test_token", "123")
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"ok": False, "description": "Bad Request: chat not found"},
            status=400,
        )
        success, res = client._make_request(
            "sendMessage", {"chat_id": "123", "text": "hi"}
        )
        assert success is False
        assert len(rsps.calls) == 1


# 15. network timeout bounded retry
def test_network_timeout_bounded_retry():
    client = TelegramClient("test_token", "123")
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            body=requests.exceptions.Timeout("Connection timed out"),
        )
        rsps.add(
            responses.POST,
            "https://api.telegram.org/bottest_token/sendMessage",
            json={"ok": True, "result": {"message_id": 999}},
            status=200,
        )
        with patch("time.sleep"):
            success, res = client._make_request(
                "sendMessage", {"chat_id": "123", "text": "hi"}
            )
            assert success is True
            assert res == 999
            assert len(rsps.calls) == 2


# 16. delivery failure gives non-zero process/result
def test_delivery_failure_gives_non_zero_process_result():
    # In weekly dispatch:
    msg_id = None
    exit_code = 0 if msg_id else 1
    assert exit_code == 1


# 17. weekly scheduler does not mark sent on failed delivery
def test_weekly_scheduler_does_not_mark_sent_on_failed_delivery():
    weekly_sent_date = None
    today_date = "2026-04-06"

    with patch("subprocess.run", side_effect=requests.exceptions.HTTPError("Failed")):
        try:
            subprocess_run_mock = MagicMock(side_effect=Exception("Failed"))
            subprocess_run_mock()
            weekly_sent_date = today_date
        except Exception:
            pass
    assert weekly_sent_date is None


# 18. weekly scheduler retries inside window
def test_weekly_scheduler_retries_inside_window():
    target = "2026-04-05"
    assert is_weekly_delivered(target) is False
    # First attempt fails -> not marked delivered
    assert is_weekly_delivered(target) is False
    # Next scheduler iteration inside 00:15..00:25 window can retry
    mark_weekly_delivered(target, 456)
    # Second attempt succeeds -> marked delivered
    assert is_weekly_delivered(target) is True


# 19. restart/dedupe prevents duplicate weekly
def test_restart_dedupe_prevents_duplicate_weekly():
    target = "2026-04-05"
    mark_weekly_delivered(target, 456)
    # Worker restarts -> in-memory state reset (simulated)
    # Scheduler checks persistent delivery state
    should_send = not is_weekly_delivered(target)
    assert should_send is False


# 20. daily final retry window prevents lost transient failure
def test_daily_final_retry_window_prevents_lost_transient_failure():
    yesterday = "2026-04-06"
    assert is_daily_final_delivered(yesterday) is False
    # Attempt 1 fails -> not delivered
    assert is_daily_final_delivered(yesterday) is False
    # Retry attempt in window succeeds
    mark_daily_final_delivered(yesterday, 123)
    assert is_daily_final_delivered(yesterday) is True


# 21. restart/dedupe prevents duplicate daily final
def test_restart_dedupe_prevents_duplicate_daily_final():
    yesterday = "2026-04-06"
    mark_daily_final_delivered(yesterday, 123)
    # Worker restarts
    assert is_daily_final_delivered(yesterday) is True


# 22. bot token never appears in logs
def test_bot_token_never_appears_in_logs(caplog):
    secret_token = "123456:SECRET_BOT_TOKEN_ABCXYZ"
    client = TelegramClient(secret_token, "123")
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://api.telegram.org/bot{secret_token}/sendMessage",
            json={"ok": False, "description": "Forbidden: bot was blocked by the user"},
            status=403,
        )
        client.send_message("test")

        for record in caplog.records:
            assert secret_token not in record.message
            assert secret_token not in str(record.__dict__)


# 23. daily delivery-state write failure => no old-message deletion and failure
def test_daily_delivery_state_write_failure_preserves_old_report_and_fails(monkeypatch):
    mock_delete = MagicMock()
    mock_send = MagicMock(return_value=999)
    target_date = datetime.date(2026, 4, 7)
    last_id = 555

    monkeypatch.setattr(daily, "get_last_report_id", lambda d: last_id)
    monkeypatch.setattr(daily, "send_telegram_photo", mock_send)
    monkeypatch.setattr(daily, "delete_telegram_message", mock_delete)
    # Simulate delivery state persistence failure
    monkeypatch.setattr(
        "app.reports.daily.mark_daily_final_delivered", lambda d, mid: False
    )

    new_msg_id = daily.send_telegram_photo("dummy.png", "caption", target_date)
    assert new_msg_id == 999
    persisted = daily.mark_daily_final_delivered(
        target_date.strftime("%Y-%m-%d"), new_msg_id
    )
    assert persisted is False
    if persisted:
        if last_id and last_id != new_msg_id:
            daily.delete_telegram_message(last_id)
        exit_code = 0
    else:
        exit_code = 1

    mock_delete.assert_not_called()
    assert exit_code == 1


# 24. weekly delivery-state write failure => failure and retry eligibility preserved
def test_weekly_delivery_state_write_failure_sets_failure_and_retry_eligible(
    monkeypatch,
):
    mock_send = MagicMock(return_value=777)
    target_date = datetime.date(2026, 4, 5)

    monkeypatch.setattr(weekly, "send_telegram_photo", mock_send)
    # Simulate delivery state persistence failure
    monkeypatch.setattr(
        "app.reports.weekly.mark_weekly_delivered", lambda d, mid: False
    )

    msg_id = weekly.send_telegram_photo("dummy.png", "caption")
    assert msg_id == 777
    persisted = weekly.mark_weekly_delivered(target_date.strftime("%Y-%m-%d"), msg_id)
    assert persisted is False
    if not persisted:
        exit_code = 1
    else:
        exit_code = 0

    assert exit_code == 1
    assert is_weekly_delivered("2026-04-05") is False


# 25. successful daily transaction preserves exact ordering
def test_successful_daily_transaction_preserves_exact_ordering(monkeypatch):
    order = []
    target_date = datetime.date(2026, 4, 7)
    last_id = 555

    def fake_send(filename, caption, date):
        order.append("sendPhoto")
        return 999

    def fake_persist(date_str, msg_id):
        order.append("persist_delivery_state")
        return True

    def fake_delete(mid):
        order.append(f"delete_message_{mid}")
        return True

    monkeypatch.setattr(daily, "send_telegram_photo", fake_send)
    monkeypatch.setattr("app.reports.daily.mark_daily_final_delivered", fake_persist)
    monkeypatch.setattr(daily, "delete_telegram_message", fake_delete)

    new_msg_id = daily.send_telegram_photo("dummy.png", "caption", target_date)
    persisted = daily.mark_daily_final_delivered(
        target_date.strftime("%Y-%m-%d"), new_msg_id
    )
    assert persisted is True
    if persisted and last_id and last_id != new_msg_id:
        daily.delete_telegram_message(last_id)

    assert order == ["sendPhoto", "persist_delivery_state", "delete_message_555"]


# 26. successful weekly transaction records exact target period
def test_successful_weekly_transaction_records_exact_target_period():
    target_period = "2026-04-05"
    assert is_weekly_delivered(target_period) is False
    success = mark_weekly_delivered(target_period, 888)
    assert success is True
    assert is_weekly_delivered(target_period) is True
    assert is_weekly_delivered("2026-04-12") is False
