import cachetools

from app.paths import CONFIG_FILE
from app.storage import StorageUtils

_config_cache = cachetools.TTLCache(maxsize=1, ttl=30)


def migrate_legacy_icons(cfg: dict) -> bool:
    """Migrates exact legacy default icons in config text strings.
    🟢 <b>{time} Світло з'явилося</b> -> 💡 <b>{time} Світло з'явилося</b>
    🔴 <b>{time} Світло зникло</b> -> ⚡️ <b>{time} Світло зникло</b>
    Preserves custom user strings intact.
    Returns True if modified, False otherwise.
    """
    if not isinstance(cfg, dict):
        return False
    advanced = cfg.get("advanced")
    if not isinstance(advanced, dict):
        return False
    text = advanced.get("text")
    if not isinstance(text, dict):
        return False

    modified = False
    if text.get("event_up") == "🟢 <b>{time} Світло з'явилося</b>":
        text["event_up"] = "💡 <b>{time} Світло з'явилося</b>"
        modified = True
    if text.get("event_down") == "🔴 <b>{time} Світло зникло</b>":
        text["event_down"] = "⚡️ <b>{time} Світло зникло</b>"
        modified = True
    return modified


def get_config():
    if "config" in _config_cache:
        return _config_cache["config"]
    cfg = StorageUtils.load_json_sync(CONFIG_FILE, None) or {}
    if isinstance(cfg, list):
        cfg = {}
    if migrate_legacy_icons(cfg):
        StorageUtils.save_json_sync(CONFIG_FILE, cfg)
    _config_cache["config"] = cfg
    return cfg


def invalidate_config_cache():
    _config_cache.clear()
