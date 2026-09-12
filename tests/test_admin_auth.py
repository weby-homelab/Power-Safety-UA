from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import asyncio
import hashlib

with patch("scripts.bootstrap.perform_cold_start_if_needed"):
    import app.main

client = TestClient(app.main.app)


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_auth_x_admin_token_header():
    """Verify X-Admin-Token header authenticates successfully."""
    response = client.get(
        "/api/admin/data",
        headers={"X-Admin-Token": "secret_adm_token_12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    assert "state" in data


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_auth_bearer_header():
    """Verify Authorization: Bearer <token> header authenticates successfully."""
    response = client.get(
        "/api/admin/data",
        headers={"Authorization": "Bearer secret_adm_token_12345"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "config" in data
    assert "state" in data


@patch("app.main.logger.warning")
@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_auth_query_param_token_deprecated(mock_warn):
    """Verify query parameter ?token= works with deprecation warning."""
    response = client.get(
        "/api/admin/data?token=secret_adm_token_12345",
    )
    assert response.status_code == 200
    mock_warn.assert_called_with(
        "query_param_admin_auth_deprecated",
        path="/api/admin/data",
        msg="Admin authentication via query parameter is deprecated. Use X-Admin-Token or Authorization: Bearer header instead.",
    )


@patch("app.main.logger.warning")
@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_auth_query_param_t_deprecated(mock_warn):
    """Verify query parameter ?t= works with deprecation warning."""
    response = client.get(
        "/api/admin/data?t=secret_adm_token_12345",
    )
    assert response.status_code == 200
    mock_warn.assert_called_with(
        "query_param_admin_auth_deprecated",
        path="/api/admin/data",
        msg="Admin authentication via query parameter is deprecated. Use X-Admin-Token or Authorization: Bearer header instead.",
    )


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_auth_invalid_token():
    """Verify invalid token returns 403 Forbidden."""
    response = client.get(
        "/api/admin/data",
        headers={"X-Admin-Token": "wrong_token"},
    )
    assert response.status_code == 403
    assert response.json()["status"] == "error"


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_auth_missing_token():
    """Verify missing token returns 403 Forbidden."""
    response = client.get("/api/admin/data")
    assert response.status_code == 403
    assert response.json()["status"] == "error"


@patch("app.main.state", {"admin_token": "super_secret_admin_token_abcdef"})
def test_admin_data_secret_hygiene():
    """Verify /api/admin/data does NOT return raw admin_token, but returns masked & fingerprint."""
    raw_token = "super_secret_admin_token_abcdef"
    expected_fp = f"sha256:{hashlib.sha256(raw_token.encode('utf-8')).hexdigest()[:16]}"

    response = client.get(
        "/api/admin/data",
        headers={"X-Admin-Token": raw_token},
    )
    assert response.status_code == 200
    data = response.json()

    assert "env" in data
    env = data["env"]
    # Secret hygiene: raw admin_token MUST NOT be present
    assert "admin_token" not in env
    assert env.get("has_admin_token") is True
    assert env.get("admin_token_masked") == "supe****cdef"
    assert env.get("token_fingerprint") == expected_fp


def test_first_run_admin_token_generation_no_raw_token(capsys):
    """Verify first-run token generation does NOT leak raw token to stdout/print."""
    import app.light_service

    test_state = {"status": "up", "secret_key": "test_sec"}
    with (
        patch("app.light_service.state", test_state),
        patch("app.light_service.save_state", AsyncMock()),
        patch(
            "app.light_service.StorageUtils.load_json_async", AsyncMock(return_value={})
        ),
        patch("app.light_service.logger.info") as mock_info,
    ):
        asyncio.run(app.light_service.load_state())

        captured = capsys.readouterr()
        generated_token = test_state.get("admin_token")
        assert generated_token is not None
        # Raw token MUST NOT be printed to stdout
        assert generated_token not in captured.out
        # Fingerprint MUST be printed and logged
        expected_fp = (
            f"sha256:{hashlib.sha256(generated_token.encode('utf-8')).hexdigest()[:16]}"
        )
        assert expected_fp in captured.out
        mock_info.assert_any_call(
            "first_run_admin_token_generated",
            token_fingerprint=f"sha256:{hashlib.sha256(generated_token.encode('utf-8')).hexdigest()[:16]}",
        )


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_config_post_flat_payload():
    """Verify /api/admin/config accepts flat payload from UI and saves without nested config wrapper."""
    saved_data = {}

    def mock_save_json(path, data):
        saved_data.update(data)
        return True

    flat_payload = {
        "settings": {"region": "kyiv", "groups": ["GPV36.1"], "push_interval": 40},
        "sources": {},
        "advanced": {
            "notifications": {
                "telegram_air_raid_alerts": False,
                "telegram_daily_reports": True,
            }
        },
        "ui": {"text": {"on_full": "Є СВІТЛО"}},
    }

    with (
        patch("app.main.StorageUtils.save_json_sync", side_effect=mock_save_json),
        patch("app.main.create_backup"),
    ):
        response = client.post(
            "/api/admin/config",
            json=flat_payload,
            headers={"X-Admin-Token": "secret_adm_token_12345"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "config" not in saved_data
    assert saved_data["settings"]["region"] == "kyiv"
    assert saved_data["settings"]["push_interval"] == 40
    assert saved_data["advanced"]["notifications"]["telegram_air_raid_alerts"] is False


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_config_post_masked_token_sanitization():
    """Verify /api/admin/config sanitizes masked token so it does not overwrite real credentials."""
    saved_data = {}

    def mock_save_json(path, data):
        saved_data.update(data)
        return True

    flat_payload = {
        "settings": {
            "telegram_bot_token": "7102****Js",
            "region": "kyiv",
        },
        "sources": {},
        "advanced": {},
        "ui": {},
    }

    with (
        patch("app.main.StorageUtils.save_json_sync", side_effect=mock_save_json),
        patch("app.main.create_backup"),
        patch(
            "app.config_runtime.get_config",
            return_value={"settings": {"telegram_bot_token": "valid_tok"}},
        ),
    ):
        response = client.post(
            "/api/admin/config",
            json=flat_payload,
            headers={"X-Admin-Token": "secret_adm_token_12345"},
        )
    assert response.status_code == 200
    assert saved_data["settings"]["telegram_bot_token"] == "valid_tok"


@patch("app.main.state", {"admin_token": "secret_adm_token_12345"})
def test_admin_config_post_unauthorized():
    """Verify /api/admin/config rejects unauthenticated requests."""
    response = client.post("/api/admin/config", json={})
    assert response.status_code == 403
