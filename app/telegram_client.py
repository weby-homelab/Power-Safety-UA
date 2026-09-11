import json
import re
import time
from typing import Optional
import requests
import structlog

logger = structlog.get_logger(__name__)


def _sanitize_error(value: object, token: Optional[str] = None) -> str:
    if value is None:
        return ""
    text = str(value)
    if token and str(token).strip():
        text = text.replace(str(token), "***REDACTED***")
    # Mask any telegram bot token pattern (e.g. /bot123456:ABC-DEF/ or bot<token>)
    text = re.sub(
        r"(https?://api\.telegram\.org/bot)[^/\s?]+", r"\1***REDACTED***", text
    )
    text = re.sub(r"(bot)[0-9]{5,15}:[a-zA-Z0-9_-]{20,60}", r"\1***REDACTED***", text)
    return text


class TelegramClient:
    def __init__(self, token, chat_id):
        self._real_token = token
        self.token = "***REDACTED***"
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _sanitize(self, value: object) -> str:
        return _sanitize_error(value, self._real_token)

    def _make_request(self, endpoint, payload, files=None, timeout=30, max_attempts=3):
        url = f"https://api.telegram.org/bot{self._real_token}/{endpoint}"
        start_time = time.time()
        max_total_retry_time = 25.0

        for attempt in range(1, max_attempts + 1):
            if files:
                for file_obj in files.values():
                    if hasattr(file_obj, "seek"):
                        try:
                            file_obj.seek(0)
                        except Exception:
                            pass

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

                err_desc = ""
                parameters = {}
                try:
                    res_json = r.json()
                    err_desc = res_json.get("description", "").lower()
                    parameters = res_json.get("parameters", {})
                except Exception:
                    err_desc = r.text.lower()

                # Handle 429 Too Many Requests
                if r.status_code == 429:
                    retry_after = 1.0
                    if isinstance(parameters, dict) and "retry_after" in parameters:
                        try:
                            retry_after = float(parameters["retry_after"])
                        except (ValueError, TypeError):
                            retry_after = 1.0
                    delay = min(max(retry_after, 1.0), 10.0)
                    elapsed = time.time() - start_time
                    if (
                        attempt < max_attempts
                        and (elapsed + delay) < max_total_retry_time
                    ):
                        logger.warning(
                            "Telegram rate limit 429, honoring retry_after",
                            endpoint=endpoint,
                            attempt=attempt,
                            retry_after=delay,
                        )
                        time.sleep(delay)
                        continue
                    return False, self._sanitize(f"rate limit 429: {err_desc}")

                # Handle 5xx Transient Server Errors
                if r.status_code >= 500:
                    backoff = attempt * 1.0
                    elapsed = time.time() - start_time
                    if (
                        attempt < max_attempts
                        and (elapsed + backoff) < max_total_retry_time
                    ):
                        logger.warning(
                            "Telegram server error 5xx, retrying",
                            endpoint=endpoint,
                            attempt=attempt,
                            status_code=r.status_code,
                        )
                        time.sleep(backoff)
                        continue
                    return False, self._sanitize(
                        f"server error {r.status_code}: {err_desc}"
                    )

                # Permanent 4xx errors: Do NOT retry blindly
                logger.warning(
                    "Telegram permanent client error",
                    endpoint=endpoint,
                    status_code=r.status_code,
                    error=self._sanitize(err_desc),
                )
                return False, self._sanitize(err_desc)

            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as e:
                backoff = attempt * 1.0
                elapsed = time.time() - start_time
                if (
                    attempt < max_attempts
                    and (elapsed + backoff) < max_total_retry_time
                ):
                    logger.warning(
                        "Telegram transient network error, retrying",
                        endpoint=endpoint,
                        attempt=attempt,
                        error=type(e).__name__,
                    )
                    time.sleep(backoff)
                    continue
                return False, self._sanitize(f"network error: {type(e).__name__}")
            except Exception as e:
                sanitized_msg = self._sanitize(e)
                logger.error(
                    "Telegram unexpected request error",
                    endpoint=endpoint,
                    error=sanitized_msg,
                )
                return False, sanitized_msg

        return False, "max retries exceeded"

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
            logger.warning("Failed to send message", error=self._sanitize(res))
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

        if "message to edit not found" in str(res):
            logger.info("Message deleted manually. Falling back to send_message.")
            return self.send_message(
                text, parse_mode, silent=True, reply_markup=reply_markup
            )

        if "message is not modified" in str(res):
            logger.info("Message content identical. No update needed.")
            return message_id

        logger.warning("Failed to edit message", error=self._sanitize(res))
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
                    logger.warning("Failed to send photo", error=self._sanitize(res))
                return res if success else None
        except Exception as e:
            logger.error("Error opening photo file", error=self._sanitize(e))
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

                recoverable_errors = [
                    "message to edit not found",
                    "message can't be edited",
                    "message id invalid",
                ]
                if any(err in str(res).lower() for err in recoverable_errors):
                    logger.info(
                        "Photo message cannot be edited. Falling back to send_photo.",
                        reason=self._sanitize(res),
                    )
                    return self.send_photo(photo_path, caption, parse_mode, silent=True)

                if "message is not modified" in str(res):
                    logger.info("Photo content identical. No update needed.")
                    return message_id

                logger.warning("Failed to edit photo", error=self._sanitize(res))
                return None
        except Exception as e:
            logger.error("Error opening photo file for edit", error=self._sanitize(e))
            return None

    def delete_message(self, message_id):
        payload = {"chat_id": self.chat_id, "message_id": message_id}
        success, res = self._make_request("deleteMessage", payload, timeout=10)
        if not success:
            logger.warning(
                "Failed to delete message",
                message_id=message_id,
                error=self._sanitize(res),
            )
        return success

    def answer_callback(self, callback_id, text):
        payload = {"callback_query_id": callback_id, "text": text}
        success, _ = self._make_request("answerCallbackQuery", payload, timeout=10)
        return success
