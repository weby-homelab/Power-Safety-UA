import datetime
import inspect
import json
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from app.light_service import (
    _last_typed_alert_events,
    _typed_alert_history_sync_types,
    format_air_raid_clear_message,
    format_air_raid_start_message,
    get_air_raid_alert,
    parse_alert_states,
    parse_typed_alerts,
)
from app.reports.common import (
    get_alert_color,
    get_alert_intervals,
    sort_alert_intervals_for_render,
)
from app.reports.daily import generate_chart as generate_daily_chart
from app.reports.daily import build_report_caption
from app.reports.weekly import (
    generate_weekly_chart,
    get_weekly_alerts_breakdown,
)


KYIV_TZ = ZoneInfo("Europe/Kyiv")
YELLOW_ALERT_COLOR = "#facc15"
RED_ALERT_COLOR = "#ef4444"


def _timestamp(hour, minute=0):
    return datetime.datetime(2026, 4, 6, hour, minute, tzinfo=KYIV_TZ).timestamp()


def test_parse_typed_alerts_maps_yellow_warning_level():
    records = [
        {
            "n": "🟡 Київ",
            "m": "Жовтий рівень тривоги. Прямуйте в укриття!",
        }
    ]

    result = parse_typed_alerts(records)

    assert result["type"] == "yellow"
    assert result["types"] == ["yellow"]
    assert result["city"] is True
    assert result["region"] is False


def test_parse_typed_alerts_prioritizes_red_immediate_danger():
    records = [
        {
            "n": "🟡 Київ",
            "m": "Жовтий рівень тривоги. Прямуйте в укриття!",
        },
        {
            "n": "🔴 Київ",
            "m": "Червоний рівень тривоги. Прямуйте в укриття!",
        },
    ]

    result = parse_typed_alerts(records)

    assert result["type"] == "red"
    assert result["types"] == ["yellow", "red"]
    assert result["city"] is True


def test_parse_typed_alerts_recognizes_emoji_only_red_and_rejects_bad_schema():
    assert parse_typed_alerts([{"n": "🔴 Київ"}])["type"] == "red"
    assert parse_typed_alerts([{"unexpected": "payload"}]) is None


def test_parse_alert_states_uses_red_for_legacy_official_alerts():
    result = parse_alert_states(
        {"Київська область": {"enabled": True}, "м. Київ": {"enabled": True}},
        "enabled",
    )

    assert result["city"] is True
    assert result["region"] is True
    assert result["status"] == "active"
    assert result["type"] == "red"
    assert result["types"] == ["red"]
    assert result["location"] == "м. Київ"


def test_get_air_raid_alert_returns_level_from_typed_api():
    response = Mock(status_code=200)
    response.json.return_value = {
        "alerts": [
            {
                "n": "🟡 Київ",
                "m": "Жовтий рівень тривоги. Прямуйте в укриття!",
            }
        ]
    }

    with patch("app.light_service.requests.get", return_value=response):
        result = get_air_raid_alert()

    assert result["type"] == "yellow"
    assert result["status"] == "warning"
    assert result["location"] == "м. Київ"


def test_get_alert_intervals_preserves_city_and_region_types(tmp_path):
    log_path = Path(tmp_path) / "air_raid_log.json"
    log_path.write_text(
        json.dumps(
            [
                {"timestamp": _timestamp(1), "event": "active", "alert_type": "yellow"},
                {"timestamp": _timestamp(2), "event": "active", "alert_type": "red"},
                {"timestamp": _timestamp(3), "event": "clear", "alert_type": "red"},
                {"timestamp": _timestamp(4), "event": "clear", "alert_type": "yellow"},
            ]
        ),
        encoding="utf-8",
    )

    intervals = get_alert_intervals(datetime.date(2026, 4, 6), str(tmp_path))

    assert [
        (start.hour, end.hour, alert_type) for start, end, alert_type in intervals
    ] == [
        (1, 4, "yellow"),
        (2, 3, "red"),
    ]


def test_get_alert_intervals_maps_legacy_events_to_city(tmp_path):
    log_path = Path(tmp_path) / "air_raid_log.json"
    log_path.write_text(
        json.dumps(
            [
                {"timestamp": _timestamp(5), "event": "active"},
                {"timestamp": _timestamp(6), "event": "clear"},
            ]
        ),
        encoding="utf-8",
    )

    intervals = get_alert_intervals(datetime.date(2026, 4, 6), str(tmp_path))

    assert len(intervals) == 1
    assert intervals[0][2] == "red"


def test_daily_and_weekly_chart_palettes_use_alert_levels():
    assert get_alert_color("yellow") == YELLOW_ALERT_COLOR
    assert get_alert_color("red") == RED_ALERT_COLOR
    assert "get_alert_color" in generate_daily_chart.__code__.co_names
    assert "get_alert_color" in generate_weekly_chart.__code__.co_names


def test_red_alert_interval_renders_after_yellow_overlap():
    start = datetime.datetime(2026, 4, 6, 1, tzinfo=KYIV_TZ)
    end = start + datetime.timedelta(hours=2)

    ordered = sort_alert_intervals_for_render(
        [
            (start, end, "red"),
            (start, end, "yellow"),
        ]
    )

    assert [interval[2] for interval in ordered] == ["yellow", "red"]


def test_alert_bars_keep_the_full_strip_geometry():
    daily_source = inspect.getsource(generate_daily_chart)
    weekly_source = inspect.getsource(generate_weekly_chart)

    assert "(alert_y, alert_h)" in daily_source
    assert "(y_pos - 0.18, 0.36)" in weekly_source
    assert "alert_lanes" not in daily_source
    assert "alert_lanes" not in weekly_source


def test_telegram_alert_messages_include_level():
    red_message = format_air_raid_start_message("red", "12:00", "м. Київ")
    clear_message = format_air_raid_clear_message({"red", "yellow"}, "13:00")

    assert "ЧЕРВОНИЙ РІВЕНЬ НЕБЕЗПЕКИ" in red_message
    assert "жовтий рівень" in clear_message
    assert "червоний рівень" in clear_message


def test_legacy_alert_events_do_not_suppress_typed_red_transition():
    last_events = _last_typed_alert_events(
        [
            {"timestamp": _timestamp(1), "event": "active"},
            {"timestamp": _timestamp(2), "event": "clear"},
            {"timestamp": _timestamp(3), "event": "active", "alert_type": "yellow"},
        ]
    )

    assert last_events == {"yellow": "active"}


def test_history_sync_repairs_missing_red_for_live_red_state():
    assert _typed_alert_history_sync_types({"yellow", "red"}, {"yellow": "active"}) == {
        "red"
    }


def test_daily_and_weekly_summaries_include_alert_levels(tmp_path):
    (Path(tmp_path) / "air_raid_log.json").write_text(
        json.dumps(
            [
                {"timestamp": _timestamp(1), "event": "active", "alert_type": "yellow"},
                {"timestamp": _timestamp(2), "event": "active", "alert_type": "red"},
                {"timestamp": _timestamp(3), "event": "clear", "alert_type": "red"},
                {"timestamp": _timestamp(4), "event": "clear", "alert_type": "yellow"},
            ]
        ),
        encoding="utf-8",
    )

    with patch("app.reports.daily.DATA_DIR", str(tmp_path)):
        caption, *_ = build_report_caption(
            datetime.date(2026, 4, 6),
            3600,
            0,
            [],
            datetime.datetime(2026, 4, 7, tzinfo=KYIV_TZ),
        )
    with patch("app.reports.weekly.DATA_DIR", str(tmp_path)):
        breakdown = get_weekly_alerts_breakdown(
            datetime.date(2026, 4, 6), datetime.date(2026, 4, 6)
        )

    assert "Жовтий рівень" in caption
    assert "Червоний рівень" in caption
    assert breakdown["yellow"]["count"] == 1
    assert breakdown["red"]["count"] == 1


def test_dashboard_contains_typed_alert_card_states():
    template = (Path(__file__).parents[1] / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "alert-red" in template
    assert "alert-yellow" in template
    assert "alertRed" in template
    assert "alertYellow" in template
