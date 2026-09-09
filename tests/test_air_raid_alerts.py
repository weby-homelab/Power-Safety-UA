import datetime
import inspect
import json
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import requests

from app.light_service import (
    _last_typed_alert_events,
    _typed_alert_history_sync_types,
    format_air_raid_clear_message,
    format_air_raid_start_message,
    format_level_names,
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


def test_get_air_raid_alert_falls_back_to_jaam_on_typed_api_failure():
    jaam_response = Mock(status_code=200)
    jaam_response.json.return_value = {
        "states": {
            "м. Київ": {"enabled": False},
            "Київська область": {"enabled": False},
        }
    }

    def mock_get(url, *args, **kwargs):
        if "alerts.in.ua" in url:
            raise requests.exceptions.ConnectionError("Connection failed")
        if "jaam.net.ua" in url:
            return jaam_response
        raise requests.exceptions.ConnectionError("Other API failed")

    with patch("app.light_service.requests.get", side_effect=mock_get):
        result = get_air_raid_alert()

    assert result["type"] == "clear"
    assert result["status"] == "clear"
    assert result["location"] == "Тривоги немає"


def test_get_air_raid_alert_falls_through_on_invalid_typed_schema():
    bad_typed_response = Mock(status_code=200)
    bad_typed_response.json.return_value = {"alerts": [{"unrecognized": "data"}]}

    jaam_response = Mock(status_code=200)
    jaam_response.json.return_value = {
        "states": {
            "м. Київ": {"enabled": True},
            "Київська область": {"enabled": False},
        }
    }

    def mock_get(url, *args, **kwargs):
        if "alerts.in.ua" in url:
            return bad_typed_response
        if "jaam.net.ua" in url:
            return jaam_response
        raise requests.exceptions.ConnectionError("Other API failed")

    with patch("app.light_service.requests.get", side_effect=mock_get):
        result = get_air_raid_alert()

    assert result["type"] == "red"
    assert result["status"] == "active"
    assert result["location"] == "м. Київ"


def test_format_level_names():
    assert format_level_names({"yellow"}) == "жовтий рівень"
    assert format_level_names({"red"}) == "червоний рівень"
    assert format_level_names({"yellow", "red"}) in (
        "жовтий рівень, червоний рівень",
        "червоний рівень, жовтий рівень",
    )
    assert format_level_names(set()) == ""


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


@patch("app.light_service.send_telegram")
@patch("app.light_service.save_state", return_value=True)
@patch("app.light_service.StorageUtils.save_json_async", return_value=True)
def test_alert_downgrade_from_red_to_yellow_message(
    mock_save_log, mock_save_state, mock_send_tg
):
    import asyncio
    from app.light_service import _alerts_loop_iteration, state

    initial_state = {
        "alert_status": "active",
        "alert_type": "red",
        "alert_types": ["red", "yellow"],
        "alert_start_time": datetime.datetime.now(KYIV_TZ).timestamp() - 1800,
    }
    state.update(initial_state)

    async def mock_load_json(path, default=None):
        if "state" in path:
            return dict(initial_state)
        if "air_raid_log" in path:
            return [
                {"event": "active", "alert_type": "yellow"},
                {"event": "active", "alert_type": "red"},
            ]
        return default

    yellow_only_alert = {
        "city": True,
        "region": False,
        "status": "warning",
        "type": "yellow",
        "types": ["yellow"],
        "location": "м. Київ",
    }

    with patch(
        "app.light_service.StorageUtils.load_json_async", side_effect=mock_load_json
    ):
        with patch(
            "app.light_service.get_air_raid_alert", return_value=yellow_only_alert
        ):
            with patch("app.light_service.load_state", return_value=None):
                with patch(
                    "app.light_service.get_config",
                    return_value={
                        "advanced": {
                            "notifications": {"telegram_air_raid_alerts": True}
                        }
                    },
                ):
                    asyncio.run(_alerts_loop_iteration())

    mock_send_tg.assert_called_once()
    sent_msg = mock_send_tg.call_args[0][0]
    assert "ВІДБІЙ ТРИВОГИ (червоний рівень)" in sent_msg
    assert "Залишається жовтий рівень попередження" in sent_msg
    assert state["alert_type"] == "yellow"
    assert state["alert_types"] == ["yellow"]


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


def test_parse_typed_alerts_rejects_stale_ghost_records():
    fixed_now = 1788950000.0  # reference epoch
    fixed_now_s = int(fixed_now - 1640000000)

    stale_records = [
        {
            "n": "🔴 Київ",
            "m": "Червоний рівень тривоги. Прямуйте в укриття!",
            "s": fixed_now_s - (24 * 3600),  # 24 hours old
        },
        {
            "n": "🟡 Київ",
            "m": "Жовтий рівень тривоги. Прямуйте в укриття!",
            "s": fixed_now_s - (40 * 3600),  # 40 hours old
        },
    ]

    result = parse_typed_alerts(stale_records, current_time=fixed_now)

    assert result["type"] == "clear"
    assert result["status"] == "clear"
    assert result["city"] is False
    assert result["region"] is False
    assert result["location"] == "Тривоги немає"


def test_parse_typed_alerts_accepts_fresh_timestamped_records():
    fixed_now = 1788950000.0
    fixed_now_s = int(fixed_now - 1640000000)

    fresh_records = [
        {
            "n": "🔴 Київ",
            "m": "Червоний рівень тривоги. Прямуйте в укриття!",
            "s": fixed_now_s - 300,  # 5 minutes old
        }
    ]

    result = parse_typed_alerts(fresh_records, current_time=fixed_now)

    assert result["type"] == "red"
    assert result["status"] == "active"
    assert result["city"] is True
    assert result["location"] == "м. Київ"


def test_parse_alert_states_supports_kyiv_without_prefix():
    jaam_states = {
        "Київ": {"enabled": True},
        "Київська область": {"enabled": False},
    }

    result = parse_alert_states(jaam_states, "enabled")

    assert result["city"] is True
    assert result["region"] is False
    assert result["status"] == "active"
    assert result["type"] == "red"
    assert result["location"] == "м. Київ"


def test_get_air_raid_alert_cross_checks_jaam_when_typed_clear():
    # Typed API has only stale alerts (effectively clear)
    fixed_now = 1788950000.0
    fixed_now_s = int(fixed_now - 1640000000)

    typed_resp = Mock(status_code=200)
    typed_resp.json.return_value = {
        "alerts": [
            {
                "n": "🔴 Київ",
                "m": "Червоний рівень тривоги",
                "s": fixed_now_s - (40 * 3600),  # stale
            }
        ]
    }

    jaam_resp = Mock(status_code=200)
    jaam_resp.json.return_value = {
        "states": {
            "Київ": {"enabled": True},
            "Київська область": {"enabled": False},
        }
    }

    def mock_get(url, *args, **kwargs):
        if "alerts.in.ua" in url:
            return typed_resp
        if "jaam.net.ua" in url:
            return jaam_resp
        raise requests.exceptions.ConnectionError("Mocked failure")

    with (
        patch("app.light_service.requests.get", side_effect=mock_get),
        patch("time.time", return_value=fixed_now),
    ):
        result = get_air_raid_alert()

    assert result["city"] is True
    assert result["status"] == "active"
    assert result["type"] == "red"
    assert result["location"] == "м. Київ"
