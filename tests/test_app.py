from fastapi.testclient import TestClient
import datetime
import asyncio
from unittest.mock import AsyncMock, patch

# Mock some dependencies before importing app
with patch("scripts.bootstrap.perform_cold_start_if_needed"):
    import app.main

client = TestClient(app.main.app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("app.main.state")
@patch("app.main.secrets.compare_digest", return_value=True)
def test_push_api_valid_key(mock_compare, mock_state):
    mock_state.get.side_effect = lambda k, d=None: (
        "valid_key" if k == "secret_key" else d
    )

    response = client.get("/api/push/valid_key")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["msg"] == "heartbeat_received"


@patch("app.main.state")
@patch("app.main.secrets.compare_digest", return_value=False)
def test_push_api_invalid_key(mock_compare, mock_state):
    mock_state.get.side_effect = lambda k, d=None: (
        "actual_key" if k == "secret_key" else d
    )

    response = client.get("/api/push/invalid_key")
    assert response.status_code == 403
    assert response.json()["status"] == "error"
    assert response.json()["msg"] == "invalid_key"


@patch("app.main.api_status")
def test_api_status_endpoint(mock_api_status):
    mock_api_status.return_value = {"status": "up", "last_seen": 12345}
    response = client.get("/api/status")
    assert response.status_code == 200


@patch("app.main.get_power_events_data")
def test_root_endpoint(mock_events):
    mock_events.return_value = [{"event": "up", "timestamp": 12345}]
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "power_safety_active_sse_connections" in response.text


def test_get_wind_label_localization():
    assert app.main.get_wind_label(0, lang="ua") == "Пн"
    assert app.main.get_wind_label(0, lang="en") == "N"
    assert app.main.get_wind_label(45, lang="ua") == "ПнСх"
    assert app.main.get_wind_label(45, lang="en") == "NE"


def test_render_day_schedule_html_localization():
    slots = [True] * 24 + [False] * 24
    date_obj = datetime.date(2026, 6, 5)

    html_ua = app.main.render_day_schedule_html(slots, date_obj, lang="ua")
    html_en = app.main.render_day_schedule_html(slots, date_obj, lang="en")

    assert "Червня" in html_ua
    assert "June" in html_en
    assert "Power ON" in html_en
    assert "Power ON 💡" in html_en
    assert "Power OFF ⚡️" in html_en
    assert "Увімкнення" in html_ua


def test_webhook_no_secret_rejected():
    """Webhook without secret token should be rejected."""
    with patch("app.main.settings.telegram_webhook_secret", "test_secret"):
        response = client.post("/api/tg/webhook", json={"test": 1})
        assert response.status_code == 403


def test_webhook_empty_body():
    """Webhook with empty body should return 503 (fail-closed)."""
    with patch("app.main.settings.telegram_webhook_secret", ""):
        response = client.post("/api/tg/webhook")
        assert response.status_code == 503


def test_rate_limit_admin_endpoint():
    """Admin endpoints should require valid auth token."""
    response = client.post(
        "/api/admin/logs/add",
        json={"event": "up", "timestamp": 1234567890.0},
        headers={"X-Admin-Token": "invalid"},
    )
    assert response.status_code in [403, 429]


@patch("app.main.state")
@patch("app.main.secrets.compare_digest", return_value=True)
@patch("app.main.load_state")
@patch("app.main.save_state")
@patch("app.main.log_event")
def test_safety_net_react_down(
    mock_log, mock_save, mock_load, mock_compare, mock_state
):
    """C1: safety_net_react with action=down should be accepted."""
    mock_state.get.side_effect = lambda k, d=None: (
        "valid_token" if k == "admin_token" else 0.0
    )
    response = client.post(
        "/api/admin/safety_net/react",
        json={"action": "down", "value": 30},
        headers={"X-Admin-Token": "valid_token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("app.main.state")
@patch("app.main.secrets.compare_digest", return_value=True)
@patch("app.main.load_state")
@patch("app.main.save_state")
def test_safety_net_react_tech(mock_save, mock_load, mock_compare, mock_state):
    """C1: safety_net_react with action=tech should be accepted."""
    mock_state.get.side_effect = lambda k, d=None: (
        "valid_token" if k == "admin_token" else 0.0
    )
    response = client.post(
        "/api/admin/safety_net/react",
        json={"action": "tech", "value": 60},
        headers={"X-Admin-Token": "valid_token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("app.main.state")
@patch("app.main.secrets.compare_digest", return_value=True)
@patch("app.main.load_state")
@patch("app.main.save_state")
def test_safety_net_react_dontknow(mock_save, mock_load, mock_compare, mock_state):
    """C1: safety_net_react with action=dontknow should be accepted."""
    mock_state.get.side_effect = lambda k, d=None: (
        "valid_token" if k == "admin_token" else 0.0
    )
    response = client.post(
        "/api/admin/safety_net/react",
        json={"action": "dontknow"},
        headers={"X-Admin-Token": "valid_token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_safety_net_react_invalid_action():
    """C1: invalid action should return 422."""
    response = client.post(
        "/api/admin/safety_net/react",
        json={"action": "invalid"},
        headers={"X-Admin-Token": "any"},
    )
    assert response.status_code == 422


@patch("app.main.state")
@patch("app.main.secrets.compare_digest", return_value=False)
def test_safety_net_react_invalid_token(mock_compare, mock_state):
    """Safety net react with invalid token should return 403."""
    mock_state.get.side_effect = lambda k, d=None: (
        "real_token" if k == "admin_token" else d
    )
    response = client.post(
        "/api/admin/safety_net/react",
        json={"action": "down"},
        headers={"X-Admin-Token": "bad_token"},
    )
    assert response.status_code == 403


def test_service_worker_assets_availability():
    """Verify all assets declared in service-worker.js return HTTP 200."""
    sw_response = client.get("/service-worker.js")
    assert sw_response.status_code == 200
    sw_text = sw_response.text

    # Extract asset paths from the JS array
    import re

    match = re.search(r"const ASSETS = \[(.*?)\];", sw_text, re.DOTALL)
    assert match is not None, "ASSETS array not found in service-worker.js"
    assets = [
        line.strip().strip("'\",")
        for line in match.group(1).splitlines()
        if line.strip().strip("'\",")
    ]

    for asset in assets:
        resp = client.get(asset)
        assert resp.status_code == 200, f"Asset {asset} returned {resp.status_code}"


@patch("app.main.get_power_events_data")
def test_index_html_buttons_and_lang(mock_events):
    """Verify index.html contains bell-btn and lang-btn with expected initial next language."""
    mock_events.return_value = []
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert 'id="bell-btn"' in html
    assert 'id="lang-btn"' in html
    assert ">EN</div>" in html
    assert "toggleNotifications()" in html
    assert "toggleLang()" in html


def test_api_status_keeps_legacy_light_and_exposes_unknown_state():
    original_status = app.main.state.get("status")
    original_cache = app.main._api_status_cache
    app.main.state["status"] = "unknown"
    app.main._api_status_cache = None

    async def fake_to_thread(func, *args, **kwargs):
        name = getattr(func, "__name__", "")
        if name == "get_today_schedule_text":
            return "schedule"
        if name == "get_air_raid_alert":
            return {
                "type": "clear",
                "status": "clear",
                "types": [],
                "location": "Тривоги немає",
            }
        if name == "_read_group_name":
            return "G1"
        if name == "_read_schedule_slots":
            return [True] * 48
        if name == "_read_schedule_slots_with_status":
            return [True] * 48, False
        raise AssertionError(f"Unexpected worker function: {name}")

    def fake_setting(section, key, default=None):
        if key in {"show_aq", "show_radiation"}:
            return False
        return default

    try:
        with (
            patch.object(app.main, "load_state", new=AsyncMock()),
            patch.object(
                app.main,
                "get_power_events_data",
                new=AsyncMock(return_value=("latest", [])),
            ),
            patch.object(app.main, "get_advanced_setting", side_effect=fake_setting),
            patch.object(app.main.asyncio, "to_thread", new=fake_to_thread),
        ):
            result = asyncio.run(app.main.api_status(lang="en"))
    finally:
        app.main.state["status"] = original_status
        app.main._api_status_cache = original_cache

    assert result["light"] == "off"
    assert result["light_state"] == "unknown"
    assert result["alert"]["type"] == "clear"


def test_schedule_reader_keeps_legacy_slots_and_reports_missing_data():
    with patch("app.main.os.path.exists", return_value=False):
        slots, schedule_known = app.main._read_schedule_slots_with_status()

    assert slots == [True] * 48
    assert schedule_known is False
