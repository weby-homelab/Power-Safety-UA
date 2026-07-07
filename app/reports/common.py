import json
import os
import datetime
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")

DAYS_UA = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]


def get_alert_intervals(target_date, data_dir):
    log_file = os.path.join(data_dir, "air_raid_log.json")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            data = json.load(f)
    except Exception:
        return []

    intervals = []
    current_start = None

    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
        tzinfo=KYIV_TZ
    )
    day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(
        tzinfo=KYIV_TZ
    )

    for event in data:
        dt = datetime.datetime.fromtimestamp(event["timestamp"], tz=KYIV_TZ)
        if event["event"] == "active":
            if current_start is None:
                current_start = dt
        elif event["event"] == "clear":
            if current_start is not None:
                start = max(current_start, day_start)
                end = min(dt, day_end)
                if start < end:
                    intervals.append((start, end, True))
                current_start = None

    if current_start is not None:
        start = max(current_start, day_start)
        now = datetime.datetime.now(KYIV_TZ)
        end = min(now, day_end)
        if start < end:
            intervals.append((start, end, True))

    return intervals
