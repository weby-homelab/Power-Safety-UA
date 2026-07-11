import structlog
import os
import json
import httpx
import asyncio
import time
import ipaddress
import socket
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
from urllib.parse import urlparse
import aiofiles

logger = structlog.get_logger(__name__)


def get_timezone():
    try:
        data_dir = os.environ.get("DATA_DIR", ".")
        config_path = os.path.join(data_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                cfg = json.load(f)
                tz_name = cfg.get("settings", {}).get("timezone", "Europe/Kyiv")
                return ZoneInfo(tz_name)
    except Exception:
        pass
    return ZoneInfo("Europe/Kyiv")


KYIV_TZ = get_timezone()
GITHUB_URL = "https://raw.githubusercontent.com/Baskerville42/outage-data-ua/main/data/{region}.json"
YASNO_URL = "https://app.yasno.ua/api/blackout-service/public/shutdowns/regions/{region_id}/dsos/{dso_id}/planned-outages"


# --- Circuit Breaker Pattern for Yasno API ---
class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_failure_time = 0

    def can_execute(self):
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
                return True
            return False
        if self.state == "HALF-OPEN":
            return False  # Only one request should try when HALF-OPEN
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
        else:
            self.state = "CLOSED"


yasno_cb = CircuitBreaker()


async def fetch_github(client: httpx.AsyncClient, cfg: dict) -> Optional[dict]:
    if not cfg.get("sources", {}).get("github", {}).get("enabled", False):
        return None
    try:
        url = GITHUB_URL.format(region=cfg["settings"].get("region", "kyiv"))
        r = await client.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"GitHub fetch error: {e}")
        return None


async def fetch_yasno(
    client: httpx.AsyncClient, cfg: dict, source_id: str = "yasno"
) -> Optional[dict]:
    yasno_cfg = cfg.get("sources", {}).get(source_id, {})
    if not yasno_cfg.get("enabled", False):
        return None

    if not yasno_cb.can_execute():
        logger.info(f"Yasno API Circuit Breaker is {yasno_cb.state}. Skipping request.")
        return None

    try:
        # Get IDs from config with defaults for Kyiv
        region_id = str(yasno_cfg.get("region_id", "25"))
        dso_id = str(yasno_cfg.get("dso_id", "902"))

        # Security validation: Ensure IDs are numeric to prevent URL manipulation
        if not (region_id.isdigit() and dso_id.isdigit()):
            logger.info(
                f"Yasno fetch error: Invalid IDs in config for {source_id} (region={region_id}, dso={dso_id})"
            )
            return None

        url = YASNO_URL.format(region_id=region_id, dso_id=dso_id)

        r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()

        yasno_cb.record_success()
        return r.json()
    except Exception as e:
        logger.error(f"Yasno fetch error ({source_id}): {e}")
        yasno_cb.record_failure()
        return None


_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT (RFC 6598)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _is_private_host(hostname: str) -> bool:
    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            addrs = socket.getaddrinfo(
                hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM
            )
        except socket.gaierror:
            return True
        ips = {a[4][0] for a in addrs}
    else:
        ips = {str(addr)}

    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return True
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                return True
    return False


async def fetch_custom(client: httpx.AsyncClient, cfg: dict) -> Optional[dict]:
    custom_url = cfg.get("advanced", {}).get("data_sources", {}).get("custom_url")
    if not custom_url:
        return None
    parsed = urlparse(custom_url)
    if parsed.scheme not in ["http", "https"]:
        return None
    if not parsed.hostname or _is_private_host(parsed.hostname):
        return None
    try:
        from app._version import get_version

        r = await client.get(
            custom_url,
            headers={"User-Agent": f"Power-Safety-UA/{get_version()}"},
            timeout=20,
            follow_redirects=False,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error(f"Custom URL fetch error: {e}")
        return None


def parse_github_day(day_data: dict) -> list[bool]:
    slots = []
    for h in range(1, 25):
        s = day_data.get(str(h), "yes")
        if s == "yes":
            slots.extend([True, True])
        elif s == "no":
            slots.extend([False, False])
        elif s == "first":
            slots.extend([False, True])
        elif s == "second":
            slots.extend([True, False])
        else:
            slots.extend([True, True])
    return slots


def extract_github(data: dict, cfg: dict) -> dict:
    res = {}
    if not data:
        return res
    fact = data.get("fact", {}).get("data", {})
    if isinstance(fact, list):
        fact = {}
    preset = data.get("preset", {}).get("data", {})

    now = datetime.now(KYIV_TZ)
    dates_to_populate = [now, now + timedelta(days=1), now + timedelta(days=2)]

    for grp in cfg["settings"].get("groups", []):
        res[grp] = {}
        for dt in dates_to_populate:
            d_str = dt.strftime("%Y-%m-%d")

            # 1. Try to find date in fact overrides
            found_in_fact = False
            for ts, group_data in fact.items():
                try:
                    f_dt = datetime.fromtimestamp(int(ts), tz=KYIV_TZ)
                    if f_dt.strftime("%Y-%m-%d") == d_str:
                        d = group_data.get(grp)
                        if d:
                            if all(d.get(str(h), "yes") == "yes" for h in range(1, 25)):
                                res[grp][d_str] = {
                                    "slots": [True] * 48,
                                    "status": "normal",
                                }
                            else:
                                res[grp][d_str] = {
                                    "slots": parse_github_day(d),
                                    "status": "normal",
                                }
                            found_in_fact = True
                            break
                except (ValueError, TypeError):
                    continue

            # 2. If not found in fact, fall back to preset
            if not found_in_fact:
                day_num = str(dt.isoweekday())  # 1=Monday, ..., 7=Sunday
                d = preset.get(grp, {}).get(day_num)
                if d:
                    res[grp][d_str] = {"slots": parse_github_day(d), "status": "normal"}

    return res


def extract_yasno(data: dict, cfg: dict) -> dict:
    res = {}
    if not data:
        return res
    for grp in cfg["settings"].get("groups", []):
        key = grp.replace("GPV", "")
        if key not in data:
            continue
        res[grp] = {}
        for day in ["today", "tomorrow"]:
            d = data[key].get(day)
            if not d or "date" not in d:
                continue
            dt = datetime.fromisoformat(d["date"])
            d_str = dt.strftime("%Y-%m-%d")
            status = d.get("status", "")
            if status == "EmergencyShutdowns":
                res[grp][d_str] = {"slots": None, "status": "emergency"}
            elif status == "NoOutages":
                # If Yasno says NoOutages, it means full light (48 slots of True)
                res[grp][d_str] = {"slots": [True] * 48, "status": "normal"}
            elif not d.get("slots"):
                res[grp][d_str] = {"slots": None, "status": "pending"}
            else:
                slots = [True] * 48
                for s in d["slots"]:
                    start, end = s.get("start", 0) // 30, s.get("end", 0) // 30
                    is_on = s.get("type") == "NotPlanned"
                    for i in range(start, min(end, 48)):
                        slots[i] = is_on
                res[grp][d_str] = {"slots": slots, "status": "normal"}
    return res


def has_schedule_changed(old_cache: dict, new_cache: dict) -> bool:
    if not old_cache:
        return False

    for source in ["yasno", "github", "custom"]:
        if source not in new_cache:
            continue

        old_src = old_cache.get(source, {})
        new_src = new_cache[source]

        if not old_src:
            continue

        for group, new_dates in new_src.items():
            old_dates = old_src.get(group, {})
            for date_str, new_data in new_dates.items():
                old_data = old_dates.get(date_str)
                if not old_data or old_data.get("slots") != new_data.get("slots"):
                    return True
    return False


async def update_local_schedules(config_path: str, output_path: str):
    try:
        async with aiofiles.open(config_path, "r") as f:
            content = await f.read()
            cfg = json.loads(content)

        async with httpx.AsyncClient() as client:
            gh_task = fetch_github(client, cfg)
            ys_task = fetch_yasno(client, cfg)
            cu_task = fetch_custom(client, cfg)

            gh_data, ys_data, cu_data = await asyncio.gather(gh_task, ys_task, cu_task)

        github_cache = extract_github(gh_data, cfg)
        yasno_cache = extract_yasno(ys_data, cfg)

        # Simple extraction for custom source: assume it's already in {group: {date: {slots, status}}} format
        custom_cache = {}
        if cu_data:
            for grp in cfg["settings"].get("groups", []):
                if grp in cu_data:
                    custom_cache[grp] = cu_data[grp]

        old_cache = {}
        if os.path.exists(output_path):
            try:
                async with aiofiles.open(output_path, "r") as f:
                    content = await f.read()
                    old_cache = json.loads(content)
            except Exception:
                pass

        new_cache = {}
        if github_cache:
            new_cache["github"] = github_cache
        if yasno_cache:
            new_cache["yasno"] = yasno_cache
        if custom_cache:
            new_cache["custom"] = custom_cache

        # Graceful degradation: if all are empty but we have old data, return stale data
        if not new_cache and old_cache:
            logger.error(
                "All schedule sources failed. Degrading gracefully to cached data."
            )
            return True, False

        has_changed = has_schedule_changed(old_cache, new_cache)

        new_cache["last_update"] = datetime.now(KYIV_TZ).strftime("%Y-%m-%d %H:%M:%S")

        async with aiofiles.open(output_path, "w") as f:
            await f.write(json.dumps(new_cache, indent=2))

        # Update schedule_history.json to preserve historical plans
        data_dir = os.environ.get("DATA_DIR", ".")
        history_path = os.path.join(data_dir, "schedule_history.json")
        history = {}
        if os.path.exists(history_path):
            try:
                async with aiofiles.open(history_path, "r") as f:
                    content = await f.read()
                    history = json.loads(content)
            except Exception:
                pass

        # Collect all dates from all available caches
        all_dates = set()
        for cache in [yasno_cache, github_cache, custom_cache]:
            if cache:
                for grp in cache:
                    all_dates.update(cache[grp].keys())

        history_updated = False
        for date_str in all_dates:
            # Find merged slots for this date across all sources (False wins)
            merged_new_slots = None
            for cache in [
                custom_cache,
                yasno_cache,
                github_cache,
            ]:  # Priority: Custom > Yasno > GitHub
                if not cache:
                    continue
                # We assume all groups in a cache for the same region have similar behavior or we pick the first
                group_keys = list(cache.keys())
                if not group_keys:
                    continue
                grp = group_keys[0]
                day_data = cache[grp].get(date_str)
                if day_data and day_data.get("slots"):
                    s = day_data["slots"]
                    if merged_new_slots is None:
                        merged_new_slots = list(s)
                    else:
                        for i in range(min(len(merged_new_slots), len(s))):
                            if s[i] is False:
                                merged_new_slots[i] = False

            if merged_new_slots:
                # Protective Merge: If day exists in history, preserve ALL existing False (outage) slots.
                # Never allow a Light slot (True) to overwrite an Outage slot (False) in history.
                if date_str in history:
                    old_slots = history[date_str].get("slots", [True] * 48)
                    final_slots = [
                        (old_slots[i] if old_slots[i] is False else merged_new_slots[i])
                        for i in range(min(len(old_slots), len(merged_new_slots)))
                    ]
                    history[date_str] = {"slots": final_slots}
                else:
                    history[date_str] = {"slots": merged_new_slots}
                history_updated = True

        if history_updated:
            async with aiofiles.open(history_path, "w") as f:
                await f.write(json.dumps(history, indent=2))

        logger.info(
            f"Local schedules updated successfully at {new_cache['last_update']}. Changed: {has_changed}"
        )
        return True, has_changed
    except Exception as e:
        logger.error(f"Failed to update local schedules: {e}")
        return False, False
