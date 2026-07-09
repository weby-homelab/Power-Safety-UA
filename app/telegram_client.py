import json
import requests
import structlog

logger = structlog.get_logger(__name__)


class TelegramClient:
    def __init__(self, token, chat_id):
        self._real_token = token
        self.token = "***REDACTED***"
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _make_request(self, endpoint, payload, files=None, timeout=30):
        url = f"https://api.telegram.org/bot{self._real_token}/{endpoint}"
        try:
            r = requests.post(
                url,
                data=payload,
                json=payload if not files else None,
                files=files,
                timeout=timeout,
            )
            if r.status_code == 200:
                res = r.json()
                result_data = res.get("result", {})
                if isinstance(result_data, dict):
                    return True, result_data.get("message_id")
                return True, result_data

            err_desc = (
                r.json().get("description", "").lower()
                if r.headers.get("content-type") == "application/json"
                else r.text.lower()
            )
            return False, err_desc
        except Exception as e:
            return False, str(e)

    def send_message(self, text, parse_mode="HTML", silent=True, reply_markup=None):
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": silent,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        success, res = self._make_request("sendMessage", payload)
        if not success:
            logger.warning("Failed to send message", error=res)
        return res if success else None

    def edit_message(self, message_id, text, parse_mode="HTML", reply_markup=None):
        payload = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        success, res = self._make_request("editMessageText", payload)
        if success:
            return message_id

        if "message to edit not found" in res:
            logger.info("Message deleted manually. Falling back to send_message.")
            return self.send_message(
                text, parse_mode, silent=True, reply_markup=reply_markup
            )

        if "message is not modified" in res:
            logger.info("Message content identical. No update needed.")
            return message_id

        logger.warning("Failed to edit message", error=res)
        return None

    def send_photo(self, photo_path, caption="", parse_mode="HTML", silent=True):
        payload = {
            "chat_id": self.chat_id,
            "caption": caption,
            "parse_mode": parse_mode,
            "disable_notification": silent,
        }
        try:
            with open(photo_path, "rb") as f:
                success, res = self._make_request(
                    "sendPhoto", payload, files={"photo": f}
                )
                if not success:
                    logger.warning("Failed to send photo", error=res)
                return res if success else None
        except Exception as e:
            logger.error("Error opening photo file", error=str(e))
            return None

    def edit_photo(self, message_id, photo_path, caption="", parse_mode="HTML"):
        media_json = json.dumps(
            {
                "type": "photo",
                "media": "attach://chart",
                "caption": caption,
                "parse_mode": parse_mode,
            }
        )
        payload = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "media": media_json,
        }
        try:
            with open(photo_path, "rb") as f:
                success, res = self._make_request(
                    "editMessageMedia", payload, files={"chart": f}
                )
                if success:
                    return message_id

                if "message to edit not found" in res:
                    logger.info(
                        "Photo message deleted manually. Falling back to send_photo."
                    )
                    return self.send_photo(photo_path, caption, parse_mode, silent=True)

                if "message is not modified" in res:
                    logger.info("Photo content identical. No update needed.")
                    return message_id

                logger.warning("Failed to edit photo", error=res)
                return None
        except Exception as e:
            logger.error("Error opening photo file for edit", error=str(e))
            return None

    def delete_message(self, message_id):
        payload = {"chat_id": self.chat_id, "message_id": message_id}
        success, res = self._make_request("deleteMessage", payload, timeout=10)
        if not success:
            logger.warning("Failed to delete message", message_id=message_id, error=res)
        return success

    def answer_callback(self, callback_id, text):
        payload = {"callback_query_id": callback_id, "text": text}
        success, _ = self._make_request("answerCallbackQuery", payload, timeout=10)
        return success
