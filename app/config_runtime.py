import cachetools

from app.paths import CONFIG_FILE
from app.storage import StorageUtils

_config_cache = cachetools.TTLCache(maxsize=1, ttl=30)


def get_config():
    if "config" in _config_cache:
        return _config_cache["config"]
    cfg = StorageUtils.load_json_sync(CONFIG_FILE, None) or {}
    if isinstance(cfg, list):
        cfg = {}
    _config_cache["config"] = cfg
    return cfg


def invalidate_config_cache():
    _config_cache.clear()
