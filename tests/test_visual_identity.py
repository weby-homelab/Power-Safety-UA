import datetime
import json
import re
from pathlib import Path
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from matplotlib.axes import Axes
from PIL import Image

from app.reports import daily, weekly
from app.reports import text as text_report

from app.reports.visual import (
    ALERT_CRITICAL,
    ALERT_WARNING,
    AQI_GOOD,
    AQI_MODERATE,
    AQI_UNHEALTHY,
    HATCH_CLEAR,
    HATCH_PLAN,
    HATCH_UNKNOWN,
    PLAN_OUTAGE,
    POWER_DOWN,
    POWER_UP,
    REPORT_AQI_STRIP_HEIGHT,
    REPORT_MAIN_STRIP_HEIGHT,
    TRACK_DARK,
    TRACK_LIGHT,
    UNKNOWN_DARK,
    WEEKLY_AQI_STRIP_HEIGHT,
    WEEKLY_MAIN_STRIP_HEIGHT,
    get_aqi_color,
    get_report_palette,
    style_for_fact,
    style_for_plan,
)


ROOT = Path(__file__).parents[1]


def test_canonical_event_tokens_are_distinct():
    assert POWER_UP == "#14B8A6"
    assert POWER_DOWN == "#F43F5E"
    assert PLAN_OUTAGE == "#818CF8"
    assert ALERT_WARNING == "#F59E0B"
    assert ALERT_CRITICAL == "#EF4444"
    assert len({POWER_UP, POWER_DOWN, PLAN_OUTAGE, ALERT_WARNING, ALERT_CRITICAL}) == 5


def test_power_unknown_is_not_rendered_as_power_up():
    palette = get_report_palette("dark")

    assert style_for_fact("up", palette)["facecolors"] == POWER_UP
    assert style_for_fact("unknown", palette)["facecolors"] == UNKNOWN_DARK
    assert style_for_fact("unknown", palette)["facecolors"] != POWER_UP
    assert style_for_fact("unknown", palette)["hatch"] == HATCH_UNKNOWN


def test_power_down_uses_power_down_semantic_token():
    palette = get_report_palette("light")

    assert style_for_fact("down", palette)["facecolors"] == POWER_DOWN
    assert style_for_fact("down", palette)["facecolors"] != POWER_UP


def test_plan_outage_uses_hatch_and_normal_plan_uses_neutral_track():
    dark_palette = get_report_palette("dark")
    light_palette = get_report_palette("light")

    outage = style_for_plan(False, dark_palette)
    normal = style_for_plan(True, light_palette)

    assert outage["facecolors"] == PLAN_OUTAGE
    assert outage["hatch"] == HATCH_PLAN
    assert normal["facecolors"] == TRACK_LIGHT
    assert "hatch" not in normal
    invalid = style_for_plan(None, dark_palette)
    assert invalid["facecolors"] == UNKNOWN_DARK
    assert invalid["hatch"] == HATCH_UNKNOWN
    invalid_string = style_for_plan("false", dark_palette)
    assert invalid_string["facecolors"] == UNKNOWN_DARK


def test_aqi_thresholds_do_not_reuse_air_alert_red():
    assert get_aqi_color(None) == UNKNOWN_DARK
    assert get_aqi_color(True) == UNKNOWN_DARK
    assert get_aqi_color(-1) == UNKNOWN_DARK
    assert get_aqi_color(float("nan")) == UNKNOWN_DARK
    assert get_aqi_color(50) == AQI_GOOD
    assert get_aqi_color(51) == AQI_MODERATE
    assert get_aqi_color(100) == AQI_MODERATE
    assert get_aqi_color(101) == AQI_UNHEALTHY
    assert AQI_UNHEALTHY != ALERT_CRITICAL


def test_dashboard_semantic_tokens_match_report_tokens_in_both_themes():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    expected = {
        "--power-up": POWER_UP,
        "--power-down": POWER_DOWN,
        "--plan-outage": PLAN_OUTAGE,
        "--alert-warning": ALERT_WARNING,
        "--alert-critical": ALERT_CRITICAL,
        "--aqi-good": AQI_GOOD,
        "--aqi-moderate": AQI_MODERATE,
        "--aqi-unhealthy": AQI_UNHEALTHY,
        "--state-neutral": TRACK_DARK,
        "--state-unknown": UNKNOWN_DARK,
    }
    for name, value in expected.items():
        assert re.search(rf"{re.escape(name)}\s*:\s*{value}\b", template, re.IGNORECASE)

    assert "--state-neutral: #CBD5E1" in template
    assert "--state-unknown: #94A3B8" in template


def test_dashboard_uses_non_color_state_identity_and_quiet_alerts():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert ".status-on" in template and "var(--power-up)" in template
    assert ".status-off" in template and "var(--power-down)" in template
    assert ".status-unknown" in template and "var(--state-unknown)" in template
    assert "lightUnknown" in template
    assert "alert-clear" in template
    assert "alert-unknown" in template
    assert 'class="card alert-unknown"' in template
    assert "alertData.status === 'active'" in template
    assert "alertData.status === 'warning'" in template
    assert "alertData.status === 'unknown'" in template
    assert "alertData.status === 'clear'" in template
    assert "Kyiv" in template
    assert 'id="schedule-grid"' in template
    assert "scheduleGridLabel" in template
    assert "schedule_known" in template
    assert ".grid-cell.unknown" in template
    assert "alertType !== 'unknown'" in template
    assert "includes(alertData.type)" in template
    assert "schedule_known === true" in template
    assert "if (alertType !== 'unknown')" in template
    assert "alertPushRedDowngrade" in template
    assert "document.documentElement.lang" in template
    assert "value === null" in template
    assert "value === ''" in template
    assert "var(--alert-warning)" in template
    assert "var(--alert-critical)" in template
    assert "data.light_state" in template
    assert "repeating-linear-gradient" in template
    assert "var(--plan-outage)" in template
    assert "--chart-bg" in template
    assert "prefers-reduced-motion" in template
    assert not re.search(r"\.alert-(?:yellow|red)[^{]*\{[^}]*infinite", template)
    assert "animation: pulse-yellow" not in template
    assert "animation: pulse-red" not in template


def test_dashboard_keeps_report_image_contract_and_localized_alert_labels():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    assert "chart${themeSuffix}${langSuffix}.png" in template
    assert "weekly${themeSuffix}${langSuffix}.png" in template
    for label in (
        "alertQuiet",
        "alertRed",
        "alertYellow",
        "alertUnknown",
        "ЧЕРВОНИЙ РІВЕНЬ",
        "ЖОВТИЙ РІВЕНЬ",
        "RED LEVEL",
        "YELLOW LEVEL",
    ):
        assert label in template


def test_weekly_caption_uses_domain_icons_and_keeps_alert_breakdown():
    source = (ROOT / "app" / "reports" / "weekly.py").read_text(encoding="utf-8")

    assert "🗓️ <b>План vs Факт:</b>" in source
    assert "💡 <b>Факт" in source
    assert "🚨 <b>Повітряні тривоги" in source
    assert "Жовтий рівень" in source
    assert "Червоний рівень" in source


def test_text_schedule_report_uses_domain_icons_without_breaking_overrides():
    intervals = text_report.get_all_intervals([True, False] + [True] * 46)

    default_block = text_report.generate_day_block(True, intervals, {})
    custom_block = text_report.generate_day_block(
        True, intervals, {"ui": {"icons": {"on": "ON", "off": "OFF"}}}
    )

    assert "💡" in default_block
    assert "⚡️" in default_block
    assert "ON" in custom_block
    assert "OFF" in custom_block


KYIV_TZ = ZoneInfo("Europe/Kyiv")


def _capture_broken_barh():
    calls = []
    original = Axes.broken_barh

    def capture(self, xranges, yrange, *args, **kwargs):
        calls.append((tuple(yrange), dict(kwargs)))
        return original(self, xranges, yrange, *args, **kwargs)

    return calls, capture


def _write_report_fixture(
    data_dir: Path, target_date: datetime.date
) -> datetime.datetime:
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
        tzinfo=KYIV_TZ
    )
    (data_dir / "config.json").write_text(
        json.dumps({"sources": {"air_quality": {"lat": "50.4", "lon": "30.4"}}}),
        encoding="utf-8",
    )
    metrics = [
        {"timestamp": (day_start + datetime.timedelta(hours=4)).timestamp(), "aqi": 30},
        {
            "timestamp": (day_start + datetime.timedelta(hours=12)).timestamp(),
            "aqi": 75,
        },
        {
            "timestamp": (day_start + datetime.timedelta(hours=20)).timestamp(),
            "aqi": 150,
        },
    ]
    (data_dir / "metrics_history.json").write_text(
        json.dumps(metrics), encoding="utf-8"
    )
    return day_start


def _daily_fixture(data_dir: Path):
    target_date = datetime.date(2026, 4, 6)
    day_start = _write_report_fixture(data_dir, target_date)
    intervals = [
        (day_start, day_start + datetime.timedelta(hours=2), "unknown"),
        (
            day_start + datetime.timedelta(hours=2),
            day_start + datetime.timedelta(hours=6),
            "up",
        ),
        (
            day_start + datetime.timedelta(hours=6),
            day_start + datetime.timedelta(hours=7),
            "down",
        ),
        (
            day_start + datetime.timedelta(hours=7),
            day_start + datetime.timedelta(days=1),
            "up",
        ),
    ]
    schedule_intervals = [
        (day_start, 20.0, True),
        (day_start + datetime.timedelta(hours=20), 2.0, False),
        (day_start + datetime.timedelta(hours=22), 2.0, True),
    ]
    alert_intervals = [
        (
            day_start + datetime.timedelta(hours=1),
            day_start + datetime.timedelta(hours=3),
            "yellow",
        ),
        (
            day_start + datetime.timedelta(hours=2),
            day_start + datetime.timedelta(hours=2, minutes=30),
            "red",
        ),
    ]
    return target_date, intervals, schedule_intervals, alert_intervals


def test_daily_chart_renders_semantic_shapes_without_changing_statistics(tmp_path):
    target_date, intervals, schedule_intervals, alert_intervals = _daily_fixture(
        tmp_path
    )
    calls, capture = _capture_broken_barh()
    fixed_now = datetime.datetime(2026, 4, 7, tzinfo=KYIV_TZ)

    with (
        patch.object(daily, "DATA_DIR", str(tmp_path)),
        patch.object(daily, "get_now", return_value=fixed_now),
        patch.object(daily.plt, "savefig"),
        patch.object(Axes, "broken_barh", new=capture),
    ):
        filename, total_up, total_down = daily.generate_chart(
            target_date,
            intervals,
            schedule_intervals,
            alert_intervals,
            theme="dark",
            lang="ua",
        )

    assert filename.endswith("report_2026-04-06.png")
    assert total_up == 23 * 3600
    assert total_down == 1 * 3600

    fact_bars = [entry for entry in calls if entry[0][1] == REPORT_MAIN_STRIP_HEIGHT]
    assert any(
        kwargs.get("facecolors") == UNKNOWN_DARK
        and kwargs.get("hatch") == HATCH_UNKNOWN
        for _, kwargs in fact_bars
    )
    assert any(kwargs.get("facecolors") == POWER_UP for _, kwargs in fact_bars)
    assert any(kwargs.get("facecolors") == POWER_DOWN for _, kwargs in fact_bars)

    plan_bars = [
        (yrange, kwargs)
        for yrange, kwargs in calls
        if yrange[0] == 13.15 and yrange[1] == REPORT_MAIN_STRIP_HEIGHT
    ]
    assert any(
        kwargs.get("facecolors") == TRACK_DARK and "hatch" not in kwargs
        for _, kwargs in plan_bars
    )
    assert any(
        kwargs.get("facecolors") == PLAN_OUTAGE and kwargs.get("hatch") == HATCH_PLAN
        for _, kwargs in plan_bars
    )

    alert_bars = [
        (yrange, kwargs)
        for yrange, kwargs in calls
        if yrange[0] == 11.15 and yrange[1] == REPORT_MAIN_STRIP_HEIGHT
    ]
    assert alert_bars[0][1].get("facecolors") == TRACK_DARK
    assert alert_bars[0][1].get("hatch") == HATCH_CLEAR
    assert [kwargs.get("facecolors") for _, kwargs in alert_bars[-2:]] == [
        ALERT_WARNING,
        ALERT_CRITICAL,
    ]

    aqi_bars = [entry for entry in calls if entry[0][1] == REPORT_AQI_STRIP_HEIGHT]
    assert aqi_bars
    assert REPORT_AQI_STRIP_HEIGHT < REPORT_MAIN_STRIP_HEIGHT * 0.5


def test_daily_chart_keeps_all_dark_light_ua_en_filenames(tmp_path):
    target_date, intervals, schedule_intervals, alert_intervals = _daily_fixture(
        tmp_path
    )
    fixed_now = datetime.datetime(2026, 4, 7, tzinfo=KYIV_TZ)
    expected = {
        ("dark", "ua"): "report_2026-04-06.png",
        ("light", "ua"): "report_2026-04-06_light.png",
        ("dark", "en"): "report_2026-04-06_en.png",
        ("light", "en"): "report_2026-04-06_light_en.png",
    }

    with (
        patch.object(daily, "DATA_DIR", str(tmp_path)),
        patch.object(daily, "get_now", return_value=fixed_now),
        patch.object(daily.plt, "savefig"),
    ):
        for (theme, lang), suffix in expected.items():
            filename, _, _ = daily.generate_chart(
                target_date,
                intervals,
                schedule_intervals,
                alert_intervals,
                theme=theme,
                lang=lang,
            )
            assert filename.endswith(suffix)


def _weekly_fixture(data_dir: Path):
    target_date, intervals, _, alert_intervals = _daily_fixture(data_dir)
    schedule_slots = [True] * 40 + [False] * 8
    daily_data = [{"date": target_date, "intervals": intervals}]
    return target_date, daily_data, schedule_slots, alert_intervals


def test_weekly_chart_uses_the_same_semantic_shapes_and_thin_aqi(tmp_path):
    target_date, daily_data, schedule_slots, alert_intervals = _weekly_fixture(tmp_path)
    calls, capture = _capture_broken_barh()
    fixed_now = datetime.datetime(2026, 4, 7, tzinfo=KYIV_TZ)
    failed_aqi_response = Mock(status_code=500)

    with (
        patch.object(weekly, "DATA_DIR", str(tmp_path)),
        patch.object(weekly, "get_now", return_value=fixed_now),
        patch.object(weekly, "get_schedule_slots", return_value=schedule_slots),
        patch.object(weekly, "get_alert_intervals", return_value=alert_intervals),
        patch.object(weekly.requests, "get", return_value=failed_aqi_response),
        patch.object(weekly.plt, "savefig"),
        patch.object(Axes, "broken_barh", new=capture),
    ):
        filename = weekly.generate_weekly_chart(
            target_date, daily_data, theme="dark", lang="ua"
        )

    assert filename.endswith("weekly_report_2026-04-06.png")
    main_bars = [entry for entry in calls if entry[0][1] == WEEKLY_MAIN_STRIP_HEIGHT]
    assert any(
        kwargs.get("facecolors") == UNKNOWN_DARK
        and kwargs.get("hatch") == HATCH_UNKNOWN
        for _, kwargs in main_bars
    )
    assert any(kwargs.get("facecolors") == POWER_UP for _, kwargs in main_bars)
    assert any(kwargs.get("facecolors") == POWER_DOWN for _, kwargs in main_bars)

    plan_bars = [
        entry
        for entry in main_bars
        if entry[1].get("facecolors") in {TRACK_DARK, PLAN_OUTAGE}
    ]
    assert any(kwargs.get("facecolors") == TRACK_DARK for _, kwargs in plan_bars)
    assert any(
        kwargs.get("facecolors") == PLAN_OUTAGE and kwargs.get("hatch") == HATCH_PLAN
        for _, kwargs in plan_bars
    )

    alert_bars = [
        entry
        for entry in main_bars
        if entry[1].get("facecolors") in {TRACK_DARK, ALERT_WARNING, ALERT_CRITICAL}
    ]
    assert any(kwargs.get("hatch") == HATCH_CLEAR for _, kwargs in alert_bars)
    active_alerts = [
        kwargs.get("facecolors")
        for _, kwargs in alert_bars
        if kwargs.get("facecolors") in {ALERT_WARNING, ALERT_CRITICAL}
    ]
    assert active_alerts[-2:] == [ALERT_WARNING, ALERT_CRITICAL]

    aqi_bars = [entry for entry in calls if entry[0][1] == WEEKLY_AQI_STRIP_HEIGHT]
    assert aqi_bars
    assert WEEKLY_AQI_STRIP_HEIGHT < WEEKLY_MAIN_STRIP_HEIGHT * 0.5


def test_weekly_chart_keeps_all_dark_light_ua_en_filenames(tmp_path):
    target_date, daily_data, schedule_slots, alert_intervals = _weekly_fixture(tmp_path)
    fixed_now = datetime.datetime(2026, 4, 7, tzinfo=KYIV_TZ)
    failed_aqi_response = Mock(status_code=500)
    expected = {
        ("dark", "ua"): "weekly_report_2026-04-06.png",
        ("light", "ua"): "weekly_report_2026-04-06_light.png",
        ("dark", "en"): "weekly_report_2026-04-06_en.png",
        ("light", "en"): "weekly_report_2026-04-06_light_en.png",
    }

    with (
        patch.object(weekly, "DATA_DIR", str(tmp_path)),
        patch.object(weekly, "get_now", return_value=fixed_now),
        patch.object(weekly, "get_schedule_slots", return_value=schedule_slots),
        patch.object(weekly, "get_alert_intervals", return_value=alert_intervals),
        patch.object(weekly.requests, "get", return_value=failed_aqi_response),
        patch.object(weekly.plt, "savefig"),
    ):
        for (theme, lang), suffix in expected.items():
            filename = weekly.generate_weekly_chart(
                target_date, daily_data, theme=theme, lang=lang
            )
            assert filename.endswith(suffix)


def _color_bbox(image: Image.Image, color: tuple[int, int, int]):
    points = [
        (x, y)
        for y in range(image.height)
        for x in range(image.width)
        if image.getpixel((x, y)) == color
    ]
    assert points
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def test_real_daily_and_weekly_pngs_keep_hatches_after_downscale(tmp_path):
    target_date, intervals, schedule_intervals, alert_intervals = _daily_fixture(
        tmp_path
    )
    fixed_now = datetime.datetime(2026, 4, 7, tzinfo=KYIV_TZ)
    daily_calls, daily_capture = _capture_broken_barh()
    weekly_calls, weekly_capture = _capture_broken_barh()
    daily_path = None
    weekly_path = None

    with (
        patch.object(daily, "DATA_DIR", str(tmp_path)),
        patch.object(daily, "get_now", return_value=fixed_now),
        patch.object(daily.requests, "get", return_value=Mock(status_code=500)),
        patch.object(Axes, "broken_barh", new=daily_capture),
    ):
        daily_path, _, _ = daily.generate_chart(
            target_date,
            intervals,
            schedule_intervals,
            alert_intervals,
            theme="dark",
            lang="ua",
        )

    with (
        patch.object(weekly, "DATA_DIR", str(tmp_path)),
        patch.object(weekly, "get_now", return_value=fixed_now),
        patch.object(
            weekly, "get_schedule_slots", return_value=[True] * 40 + [False] * 8
        ),
        patch.object(weekly, "get_alert_intervals", return_value=alert_intervals),
        patch.object(weekly.requests, "get", return_value=Mock(status_code=500)),
        patch.object(Axes, "broken_barh", new=weekly_capture),
    ):
        weekly_path = weekly.generate_weekly_chart(
            target_date,
            [{"date": target_date, "intervals": intervals}],
            theme="dark",
            lang="ua",
        )

    assert any(kwargs.get("hatch") == HATCH_PLAN for _, kwargs in daily_calls)
    assert any(kwargs.get("hatch") == HATCH_UNKNOWN for _, kwargs in daily_calls)
    assert any(kwargs.get("hatch") == HATCH_PLAN for _, kwargs in weekly_calls)
    assert any(kwargs.get("hatch") == HATCH_UNKNOWN for _, kwargs in weekly_calls)

    for path, size in (
        (Path(daily_path), (1000, 280)),
        (Path(weekly_path), (1000, 550)),
    ):
        with Image.open(path) as source:
            image = source.convert("RGB")
            assert image.size == size
            assert image.getbbox() is not None
            bbox = _color_bbox(image, (129, 140, 248))
            mobile = image.resize(
                (600, round(image.height * 600 / image.width)), Image.Resampling.LANCZOS
            )
            mobile_bbox = tuple(round(value * 0.6) for value in bbox)
            mobile_crop = mobile.crop(mobile_bbox)
            assert len(set(mobile_crop.getdata())) >= 8
