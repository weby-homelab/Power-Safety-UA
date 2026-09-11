import pytest
import responses
from app.telegram_client import TelegramClient


@pytest.fixture
def client():
    return TelegramClient("dummy_token", "dummy_chat_id")


def test_send_message_success(client):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/botdummy_token/sendMessage",
            json={"ok": True, "result": {"message_id": 12345}},
            status=200,
        )
        msg_id = client.send_message("Hello World")
        assert msg_id == 12345


def test_send_message_failure(client):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/botdummy_token/sendMessage",
            json={"ok": False, "description": "Bad Request"},
            status=400,
        )
        msg_id = client.send_message("Hello World")
        assert msg_id is None


def test_edit_message_success(client):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/botdummy_token/editMessageText",
            json={"ok": True, "result": {"message_id": 12345}},
            status=200,
        )
        msg_id = client.edit_message(12345, "Updated World")
        assert msg_id == 12345


def test_delete_message_success(client):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/botdummy_token/deleteMessage",
            json={"ok": True, "result": True},
            status=200,
        )
        success = client.delete_message(12345)
        assert success is True


def test_answer_callback(client):
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            "https://api.telegram.org/botdummy_token/answerCallbackQuery",
            json={"ok": True, "result": True},
            status=200,
        )
        success = client.answer_callback("query_123", "Answer")
        assert success is True


def test_sanitize_error_removes_token_and_bot_url():
    from app.telegram_client import _sanitize_error

    secret = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456"
    leak_url = f"https://api.telegram.org/bot{secret}/sendMessage"
    msg = f"Connection failed to {leak_url} with error {secret}"

    sanitized = _sanitize_error(msg, token=secret)
    assert secret not in sanitized
    assert "bot***REDACTED***" in sanitized
    assert "***REDACTED***" in sanitized


def test_telegram_client_exception_sanitization_in_return_and_logs(caplog):
    from app.telegram_client import TelegramClient

    secret_token = "987654321:SECRET_TOKEN_VALUE_XYZ"
    client = TelegramClient(secret_token, "dummy_chat_id")

    # Construct an exception that contains the full token-bearing URL
    leak_msg = f"HTTPSConnectionPool(host='api.telegram.org', port=443): Max retries exceeded with url: /bot{secret_token}/sendMessage"
    with responses.RequestsMock() as rsps:
        rsps.add(
            responses.POST,
            f"https://api.telegram.org/bot{secret_token}/sendMessage",
            body=Exception(leak_msg),
        )
        success, err = client._make_request("sendMessage", {"text": "hi"})
        assert success is False
        # Token must NOT be in the returned error
        assert secret_token not in err
        assert "***REDACTED***" in err
