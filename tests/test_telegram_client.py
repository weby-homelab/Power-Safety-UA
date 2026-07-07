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
