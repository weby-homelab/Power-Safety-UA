import json
import os
import datetime
from zoneinfo import ZoneInfo

from app.reports.visual import ALERT_CRITICAL, ALERT_WARNING

KYIV_TZ = ZoneInfo("Europe/Kyiv")

DAYS_UA = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]

ALERT_TYPE_YELLOW = "yellow"
ALERT_TYPE_RED = "red"
ALERT_TYPES = (ALERT_TYPE_YELLOW, ALERT_TYPE_RED)
ALERT_COLORS = {
    ALERT_TYPE_YELLOW: ALERT_WARNING,
    ALERT_TYPE_RED: ALERT_CRITICAL,
}


def normalize_alert_type(value):
    """Return a supported alert level while keeping old history readable."""
    if value is True:
        return ALERT_TYPE_RED
    if value is None:
        return None
    if value is False:
        return None

    normalized = str(value).strip().lower()
    if normalized in {"yellow", "warning", "region", "potential-threat"}:
        return ALERT_TYPE_YELLOW
    if normalized in {"red", "active", "city", "alert", "immediate-danger"}:
        return ALERT_TYPE_RED
    return None


def get_alert_color(alert_type):
    return ALERT_COLORS.get(
        normalize_alert_type(alert_type), ALERT_COLORS[ALERT_TYPE_RED]
    )


def sort_alert_intervals_for_render(intervals):
    """Draw yellow first and red last so immediate danger wins overlaps."""
    return sorted(
        intervals,
        key=lambda interval: (
            normalize_alert_type(interval[2]) == ALERT_TYPE_RED,
            interval[0],
        ),
    )


def summarize_alert_intervals(intervals):
    summary = {
        alert_type: {"count": 0, "duration_sec": 0.0} for alert_type in ALERT_TYPES
    }
    for start, end, alert_type in intervals:
        normalized_type = normalize_alert_type(alert_type)
        if normalized_type is None:
            continue
        summary[normalized_type]["count"] += 1
        summary[normalized_type]["duration_sec"] += (end - start).total_seconds()
    return summary


def merged_alert_duration(intervals):
    ranges = sorted((start, end) for start, end, _ in intervals if start < end)
    if not ranges:
        return 0.0

    total = 0.0
    current_start, current_end = ranges[0]
    for start, end in ranges[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            total += (current_end - current_start).total_seconds()
            current_start, current_end = start, end
    return total + (current_end - current_start).total_seconds()


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
    current_starts = {alert_type: None for alert_type in ALERT_TYPES}

    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
        tzinfo=KYIV_TZ
    )
    day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(
        tzinfo=KYIV_TZ
    )

    valid_events = [
        item
        for item in data
        if isinstance(item, dict)
        and isinstance(item.get("timestamp"), (int, float))
        and item.get("event") in {"active", "clear"}
    ]
    for event in sorted(valid_events, key=lambda item: item["timestamp"]):
        try:
            dt = datetime.datetime.fromtimestamp(event["timestamp"], tz=KYIV_TZ)
        except (KeyError, TypeError, ValueError, OSError):
            continue

        alert_type = (
            normalize_alert_type(event["alert_type"])
            if "alert_type" in event
            else ALERT_TYPE_RED
        )
        if alert_type is None:
            continue
        if event.get("event") == "active":
            if current_starts[alert_type] is None:
                current_starts[alert_type] = dt
        elif event.get("event") == "clear":
            current_start = current_starts[alert_type]
            if current_start is not None:
                start = max(current_start, day_start)
                end = min(dt, day_end)
                if start < end:
                    intervals.append((start, end, alert_type))
                current_starts[alert_type] = None

    now = datetime.datetime.now(KYIV_TZ)
    for alert_type, current_start in current_starts.items():
        if current_start is not None:
            start = max(current_start, day_start)
            end = min(now, day_end)
            if start < end:
                intervals.append((start, end, alert_type))

    return sorted(intervals, key=lambda interval: interval[0])
