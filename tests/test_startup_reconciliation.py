import asyncio
import pytest
from unittest.mock import patch
from app.light_service import (
    reconcile_startup_state,
    _monitor_loop_iteration,
    state,
)
import app.light_service as ls


@pytest.fixture(autouse=True)
def reset_startup_reconciled():
    ls._startup_reconciled = False
    yield
    ls._startup_reconciled = False


def test_restart_stale_power_transitions_to_unknown_without_alerts():
    # Scenario 1: restart during power UP with stale last_seen (> outage threshold)
    t_now = 1775450000.0
    t_stale_last_seen = t_now - 3600.0  # 1 hour ago (> 180s)

    state.clear()
    state.update(
        {
            "status": "up",
            "last_seen": t_stale_last_seen,
            "went_down_at": 0.0,
            "came_up_at": t_now - 7200.0,
        }
    )

    captured_alerts = []
    logged_events = []

    async def mock_save_state():
        return True

    async def mock_load_state():
        return None

    async def mock_log_event(event_type, ts):
        logged_events.append((event_type, ts))

    with (
        patch("app.light_service.save_state", side_effect=mock_save_state),
        patch("app.light_service.load_state", side_effect=mock_load_state),
        patch("app.light_service.log_event", side_effect=mock_log_event),
        patch(
            "app.light_service.send_telegram",
            side_effect=lambda msg: captured_alerts.append(msg),
        ),
    ):
        changed = asyncio.run(reconcile_startup_state(current_time=t_now))

    assert changed is True
    assert state["status"] == "unknown"
    assert state.get("startup_reconciliation") is True
    assert len(captured_alerts) == 0, (
        "Must NOT emit a 'Світло зникло' Telegram alert on restart"
    )
    assert len(logged_events) == 0, "Must NOT append synthetic power-down event"

    # Verify monitor loop iteration does not trigger outage detection while unknown
    with (
        patch("app.light_service.save_state", side_effect=mock_save_state),
        patch("app.light_service.load_state", side_effect=mock_load_state),
        patch("app.light_service.log_event", side_effect=mock_log_event),
        patch(
            "app.light_service.send_telegram",
            side_effect=lambda msg: captured_alerts.append(msg),
        ),
        patch("app.light_service.get_current_time", return_value=t_now + 5.0),
    ):
        asyncio.run(_monitor_loop_iteration())

    assert state["status"] == "unknown"
    assert len(captured_alerts) == 0


def test_restart_confirmed_power_down_preserves_went_down_at():
    # Scenario 2: restart during confirmed power DOWN
    t_now = 1775450000.0
    original_went_down = t_now - 1800.0  # went down 30 mins ago

    state.clear()
    state.update(
        {
            "status": "down",
            "last_seen": original_went_down - 30.0,
            "went_down_at": original_went_down,
        }
    )

    captured_alerts = []

    async def mock_save_state():
        return True

    async def mock_load_state():
        return None

    with (
        patch("app.light_service.save_state", side_effect=mock_save_state),
        patch("app.light_service.load_state", side_effect=mock_load_state),
        patch(
            "app.light_service.send_telegram",
            side_effect=lambda msg: captured_alerts.append(msg),
        ),
    ):
        changed = asyncio.run(reconcile_startup_state(current_time=t_now))

    assert changed is False
    assert state["status"] == "down"
    assert state["went_down_at"] == original_went_down
    assert len(captured_alerts) == 0


def test_restart_rapid_reboot_preserves_up_status():
    # Scenario 3: restart during rapid reboot (< outage threshold)
    t_now = 1775450000.0
    recent_last_seen = t_now - 20.0  # 20s ago (< 180s)

    state.clear()
    state.update(
        {
            "status": "up",
            "last_seen": recent_last_seen,
            "went_down_at": 0.0,
        }
    )

    captured_alerts = []

    async def mock_save_state():
        return True

    async def mock_load_state():
        return None

    with (
        patch("app.light_service.save_state", side_effect=mock_save_state),
        patch("app.light_service.load_state", side_effect=mock_load_state),
        patch(
            "app.light_service.send_telegram",
            side_effect=lambda msg: captured_alerts.append(msg),
        ),
    ):
        changed = asyncio.run(reconcile_startup_state(current_time=t_now))

    assert changed is False
    assert state["status"] == "up"
    assert len(captured_alerts) == 0


def test_first_ping_after_stale_restart_does_not_emit_restoration_alert():
    # First ping handling after stale restart (Scenario 1 transition)
    from fastapi.testclient import TestClient
    from app.main import app

    t_now = 1775450000.0
    secret_key = "test_secret_reconciliation_key_123"

    state.clear()
    state.update(
        {
            "status": "unknown",
            "startup_reconciliation": True,
            "last_seen": t_now - 3600.0,
            "went_down_at": 0.0,
            "came_up_at": 0.0,
            "secret_key": secret_key,
        }
    )

    captured_telegrams = []

    async def mock_save_state():
        return True

    async def mock_load_state():
        return None

    with (
        patch("app.main.save_state", side_effect=mock_save_state),
        patch("app.main.load_state", side_effect=mock_load_state),
        patch(
            "app.main._safe_send_telegram",
            side_effect=lambda msg: captured_telegrams.append(msg),
        ),
        patch("app.main.broadcast_state_update", return_value=None),
    ):
        client = TestClient(app)
        resp = client.get(f"/api/ping/{secret_key}")
        assert resp.status_code == 200

    assert state["status"] == "up"
    assert state.get("startup_reconciliation") is None
    assert len(captured_telegrams) == 0, (
        "Cold start / stale restart first ping must NOT send Telegram alert"
    )


def test_first_ping_after_confirmed_down_uses_original_went_down_at():
    # First ping handling after restart during confirmed power DOWN (Scenario 2)
    from fastapi.testclient import TestClient
    from app.main import app

    t_now = 1775450000.0
    original_went_down = t_now - 7200.0  # Outage lasted 2 hours
    secret_key = "test_secret_reconciliation_key_123"

    state.clear()
    state.update(
        {
            "status": "down",
            "last_seen": original_went_down - 30.0,
            "went_down_at": original_went_down,
            "secret_key": secret_key,
            "quiet_status": "active",
        }
    )

    captured_telegrams = []

    async def mock_save_state():
        return True

    async def mock_load_state():
        return None

    with (
        patch("app.main.save_state", side_effect=mock_save_state),
        patch("app.main.load_state", side_effect=mock_load_state),
        patch(
            "app.main._safe_send_telegram",
            side_effect=lambda msg: captured_telegrams.append(msg),
        ),
        patch("app.main.broadcast_state_update", return_value=None),
        patch("time.time", return_value=t_now),
    ):
        client = TestClient(app)
        resp = client.get(f"/api/ping/{secret_key}")
        assert resp.status_code == 200

    assert state["status"] == "up"
    assert len(captured_telegrams) == 1
    sent_msg = captured_telegrams[0]
    assert "2 г" in sent_msg, (
        "Restoration message must calculate duration from original went_down_at"
    )
