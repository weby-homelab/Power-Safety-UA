import os
import datetime
import fcntl
import contextlib
from typing import Dict, Any, Optional
import structlog
from app.storage import StorageUtils

logger = structlog.get_logger(__name__)

DATA_DIR = os.environ.get("DATA_DIR", "data")


def get_delivery_state_path() -> str:
    return os.path.join(
        os.environ.get("DATA_DIR", DATA_DIR), "report_delivery_state.json"
    )


def get_delivery_lock_path() -> str:
    return os.path.join(
        os.environ.get("DATA_DIR", DATA_DIR), "report_delivery_state.lock"
    )


@contextlib.contextmanager
def delivery_state_lock():
    lock_path = get_delivery_lock_path()
    os.makedirs(os.path.dirname(os.path.abspath(lock_path)) or ".", exist_ok=True)
    handle = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
        except Exception:
            pass


def load_delivery_state() -> Dict[str, Any]:
    path = get_delivery_state_path()
    state = StorageUtils.load_json_sync(path, default=None)
    if not isinstance(state, dict):
        state = {}
    if "daily_final" not in state or not isinstance(state["daily_final"], dict):
        state["daily_final"] = {}
    if "weekly" not in state or not isinstance(state["weekly"], dict):
        state["weekly"] = {}
    return state


def save_delivery_state(state: Dict[str, Any]) -> bool:
    path = get_delivery_state_path()
    return StorageUtils.save_json_sync(path, state)


def is_daily_final_delivered(date_str: str) -> bool:
    state = load_delivery_state()
    return date_str in state.get("daily_final", {})


def mark_daily_final_delivered(date_str: str, message_id: Optional[int]) -> bool:
    with delivery_state_lock():
        state = load_delivery_state()
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        state["daily_final"][date_str] = {
            "message_id": message_id,
            "sent_at": now_ts,
        }
        # Prune daily entries older than 30 days
        try:
            current_date = datetime.date.fromisoformat(date_str)
            cutoff = current_date - datetime.timedelta(days=30)
            state["daily_final"] = {
                d: v
                for d, v in state["daily_final"].items()
                if datetime.date.fromisoformat(d) >= cutoff
            }
        except Exception as e:
            logger.warning("Error pruning daily delivery state", error=str(e))

        return save_delivery_state(state)


def is_weekly_delivered(date_str: str) -> bool:
    state = load_delivery_state()
    return date_str in state.get("weekly", {})


def mark_weekly_delivered(date_str: str, message_id: Optional[int]) -> bool:
    with delivery_state_lock():
        state = load_delivery_state()
        now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
        state["weekly"][date_str] = {
            "message_id": message_id,
            "sent_at": now_ts,
        }
        # Prune weekly entries older than 90 days
        try:
            current_date = datetime.date.fromisoformat(date_str)
            cutoff = current_date - datetime.timedelta(days=90)
            state["weekly"] = {
                d: v
                for d, v in state["weekly"].items()
                if datetime.date.fromisoformat(d) >= cutoff
            }
        except Exception as e:
            logger.warning("Error pruning weekly delivery state", error=str(e))

        return save_delivery_state(state)
