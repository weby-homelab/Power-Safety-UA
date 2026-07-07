import json
import os
import structlog
from pywebpush import webpush, WebPushException

logger = structlog.get_logger()

# VAPID configuration
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS = {
    "sub": "mailto:" + os.environ.get("VAPID_CONTACT_EMAIL", "contact@weby.guru")
}

# Storage path
from app.paths import DATA_DIR  # noqa: E402

SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "push_subscriptions.json")


def _load_subscriptions():
    if os.path.exists(SUBSCRIPTIONS_FILE):
        try:
            with open(SUBSCRIPTIONS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _save_subscriptions(subs):
    try:
        os.makedirs(os.path.dirname(SUBSCRIPTIONS_FILE), exist_ok=True)
        with open(SUBSCRIPTIONS_FILE, "w") as f:
            json.dump(subs, f, indent=2)
    except IOError as e:
        logger.error("push_subscriptions_save_error", error=str(e))


def save_subscription(subscription_info: dict) -> bool:
    subs = _load_subscriptions()
    endpoint = subscription_info.get("endpoint", "")
    # Avoid duplicates
    for s in subs:
        if s.get("endpoint") == endpoint:
            return True  # Already exists
    subs.append(subscription_info)
    _save_subscriptions(subs)
    logger.info("push_subscription_added", total=len(subs))
    return True


def remove_subscription(endpoint: str) -> bool:
    subs = _load_subscriptions()
    new_subs = [s for s in subs if s.get("endpoint") != endpoint]
    if len(new_subs) < len(subs):
        _save_subscriptions(new_subs)
        logger.info("push_subscription_removed", total=len(new_subs))
        return True
    return False


def get_subscriptions():
    return _load_subscriptions()


def send_push_notification(title: str, body: str, url: str = "/"):
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        logger.warning(
            "push_vapid_keys_missing",
            msg="Web Push disabled: VAPID keys not configured",
        )
        return 0

    subs = _load_subscriptions()
    if not subs:
        return 0

    payload = json.dumps(
        {
            "title": title,
            "body": body,
            "icon": "/static/icon-192.png",
            "badge": "/static/favicon.png",
            "url": url,
            "timestamp": __import__("time").time(),
        }
    )

    sent = 0
    expired = []

    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
            )
            sent += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                expired.append(sub.get("endpoint"))
                logger.info(
                    "push_subscription_expired", endpoint=sub.get("endpoint", "")[:50]
                )
            else:
                logger.error(
                    "push_send_error",
                    error=str(e),
                    status=getattr(e.response, "status_code", None),
                )
        except Exception as e:
            logger.error("push_send_unexpected_error", error=str(e))

    # Clean up expired subscriptions
    if expired:
        subs = [s for s in subs if s.get("endpoint") not in expired]
        _save_subscriptions(subs)

    logger.info(
        "push_notifications_sent", sent=sent, total=len(subs), expired=len(expired)
    )
    return sent
