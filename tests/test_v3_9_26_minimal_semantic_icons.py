import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.config_runtime import migrate_legacy_icons
from app.generate_daily_report import build_report_caption
from app.light_service import (
    format_air_raid_clear_message,
    format_air_raid_start_message,
    format_event_message,
)
from app.main import render_day_schedule_html
from app.reports.visual import (
    ALERT_CLEAR_ICON,
    ALERT_CRITICAL_ICON,
    ALERT_WARNING_ICON,
    POWER_DOWN_ICON,
    POWER_UP_ICON,
    UNKNOWN_ICON,
)

KYIV_TZ = ZoneInfo("Europe/Kyiv")
ROOT = Path(__file__).parents[1]


# 1. ICON CONSTANTS
def test_icon_constants_values():
    assert ALERT_WARNING_ICON == "⚠️"
    assert ALERT_CRITICAL_ICON == "🚨"
    assert ALERT_CLEAR_ICON == "🛡️"
    assert POWER_UP_ICON == "💡"
    assert "⚡" in POWER_DOWN_ICON
    assert UNKNOWN_ICON == "❔"


def test_no_double_semantic_icon_constants():
    visual_source = (ROOT / "app" / "reports" / "visual.py").read_text(encoding="utf-8")
    for double_icon in ("🟡 ⚠️", "🔴 🚨", "✅ 🛡️"):
        assert double_icon not in visual_source


# 2. DASHBOARD TEMPLATES
def test_dashboard_uses_canonical_icons_and_no_doubles():
    template = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    # Centralized ICONS constant exists
    assert "const ICONS =" in template
    assert "powerUp: '💡'" in template
    assert "warning: '⚠️'" in template
    assert "critical: '🚨'" in template
    assert "clear: '🛡️'" in template
    assert "unknown: '❔'" in template

    # No doubled icons in public dashboard
    for double_icon in ("🟡 ⚠️", "🔴 🚨", "✅ 🛡️"):
        assert double_icon not in template

    # Wind line has no 💨
    assert "💨" not in template
    assert 'windLabel: "Вітер: "' in template
    assert 'windLabel: "Wind: "' in template

    # Radiation keeps ☢️
    assert "☢️" in template

    # Section titles remain icon-free
    assert (
        '<div class="section-header" id="group-schedule-header">Графік</div>'
        in template
    )
    assert '<div class="section-header" id="aqi-loc">Якість повітря</div>' in template
    assert (
        '<div class="section-header" id="header-today">Аналітика за сьогодні</div>'
        in template
    )
    assert (
        '<div class="section-header" id="header-weekly">Тижневий звіт</div>' in template
    )

    # Notification bell remains
    assert "🔔" in template


def test_group_schedule_icons_precede_labels():
    slots = [True] * 24 + [False] * 24
    d = datetime.date(2026, 9, 11)

    html_ua = render_day_schedule_html(slots, d, lang="ua")
    assert "💡 Увімкнення" in html_ua
    assert "⚡️ Вимкнення" in html_ua or "⚡ Вимкнення" in html_ua

    html_en = render_day_schedule_html(slots, d, lang="en")
    assert "💡 Power ON" in html_en
    assert "⚡️ Power OFF" in html_en or "⚡ Power OFF" in html_en


# 3. TELEGRAM EVENTS
def test_telegram_alert_event_single_icons():
    # Yellow message starts with ⚠️ and not 🟡
    yellow_msg = format_air_raid_start_message("yellow", "10:00", "м. Київ")
    assert yellow_msg.startswith("⚠️")
    assert "🟡" not in yellow_msg

    # Red message starts with 🚨 and not 🔴
    red_msg = format_air_raid_start_message("red", "10:00", "м. Київ")
    assert red_msg.startswith("🚨")
    assert "🔴 🚨" not in red_msg
    assert not red_msg.startswith("🔴")

    # Clear message starts with 🛡️ and not ✅
    clear_msg = format_air_raid_clear_message({"yellow"}, "11:00")
    assert clear_msg.startswith("🛡️")
    assert "✅" not in clear_msg


def test_telegram_red_clear_yellow_remains():
    # When red clears but yellow remains: exactly one 🛡️ for clear, one ⚠️ for remaining
    clear_msg = format_air_raid_clear_message({"red"}, "12:00")
    remaining_msg = f"{ALERT_WARNING_ICON} Залишається жовтий рівень попередження"
    full_msg = f"{clear_msg}\n{remaining_msg}"

    assert "🛡️" in full_msg
    assert "⚠️" in full_msg
    assert "🟡 ⚠️" not in full_msg
    assert "🔴 🚨" not in full_msg
    assert full_msg.count("🛡️") == 1
    assert full_msg.count("⚠️") == 1


def test_telegram_power_events_grammar():
    now_ts = datetime.datetime(2026, 9, 11, 14, 0, tzinfo=KYIV_TZ).timestamp()
    prev_ts = now_ts - 7200

    with (
        patch(
            "app.light_service.get_next_scheduled_event",
            return_value={"time_left_sec": 3600, "interval": "15:00-18:00"},
        ),
        patch("app.light_service.get_deviation_info", return_value=None),
        patch("app.light_service.get_config", return_value={"ui": {"text": {}}}),
    ):
        up_msg = format_event_message(True, now_ts, prev_ts)
        down_msg = format_event_message(False, now_ts, prev_ts)

        # Power ON uses 💡 only in headline
        assert up_msg.startswith("💡")
        # Ensure no 🕓, 🤷‍♂️, or extra decorative icons
        for obsolete in ("🕓", "🤷‍♂️", "🌤", "🌩", "🏆", "🧟", "📝", "👉", "🕐"):
            assert obsolete not in up_msg
            assert obsolete not in down_msg

        # Power OFF uses ⚡ only in headline
        assert down_msg.startswith("⚡")

        # Plan line uses single 🗓️
        assert "🗓️" in up_msg
        assert "🗓️" in down_msg
        assert up_msg.count("🗓️") == 1
        assert down_msg.count("🗓️") == 1


# 4. DAILY CAPTION
def test_daily_caption_structure():
    target_date = datetime.date(2026, 9, 10)
    now_time = datetime.datetime(2026, 9, 10, 20, 0, tzinfo=KYIV_TZ)
    slots = [True] * 40 + [False] * 8

    caption, _, _, _ = build_report_caption(
        target_date, 20 * 3600, 4 * 3600, slots, now_time
    )

    # Exactly one 📊 title marker
    assert caption.count("📊") == 1
    # One 💡 fact-up marker
    assert caption.count("💡") == 1
    assert "💡 Світло було:" in caption
    # One ⚡ fact-down marker
    assert caption.count("⚡") == 1
    assert "⚡ Світла не було:" in caption
    # One 🗓️ plan-section marker
    assert caption.count("🗓️") == 1
    assert "🗓️ <b>План vs факт</b>" in caption
    # No decorative emoji
    for obsolete in ("👉", "🕐", "🌤", "🌩", "🏆", "🧟", "📝"):
        assert obsolete not in caption


# 5. WEEKLY CAPTION
def test_weekly_caption_structure():
    weekly_source = (ROOT / "app" / "reports" / "weekly.py").read_text(encoding="utf-8")

    # Contains minimal semantic headers
    assert "📊 <b>Енергетичний тиждень" in weekly_source
    assert "💡 Світло було:" in weekly_source
    assert "⚡ Відключення:" in weekly_source
    assert "🚨 Тривоги без подвійного рахунку:" in weekly_source
    assert "🗓️ <b>План vs факт</b>" in weekly_source

    # Free from decorative obsolete icons
    for obsolete in ("📅", "🌤", "🌩", "🏆", "🧟", "📝", "👉", "🕐"):
        assert obsolete not in weekly_source


# 6. CONFIG MIGRATION & CUSTOM TEXT PRESERVATION
def test_config_migration_and_custom_preservation():
    # Legacy default migrations in advanced and ui
    legacy_cfg = {
        "advanced": {
            "text": {
                "event_up": "🟢 <b>{time} Світло з'явилося</b>",
                "event_down": "🔴 <b>{time} Світло зникло</b>",
            }
        },
        "ui": {
            "text": {
                "next_prefix_up": "💡 Очікуємо через",
                "next_prefix_down": "❌ Вимкнення через",
            }
        },
    }
    assert migrate_legacy_icons(legacy_cfg) is True
    assert (
        legacy_cfg["advanced"]["text"]["event_up"]
        == "💡 <b>{time} Світло з'явилося</b>"
    )
    assert "⚡" in legacy_cfg["advanced"]["text"]["event_down"]
    assert legacy_cfg["ui"]["text"]["next_prefix_up"] == "🗓️ Очікуємо через"
    assert legacy_cfg["ui"]["text"]["next_prefix_down"] == "🗓️ Вимкнення через"

    # Custom text preserved intact
    custom_cfg = {
        "ui": {
            "text": {
                "event_up": "🔥 Світло увімкнено! {time}",
                "event_down": "⚠️ Вимкнули світло {time}",
                "next_prefix_up": "Буде приблизно о",
            }
        }
    }
    assert migrate_legacy_icons(custom_cfg) is False
    assert custom_cfg["ui"]["text"]["event_up"] == "🔥 Світло увімкнено! {time}"
    assert custom_cfg["ui"]["text"]["event_down"] == "⚠️ Вимкнули світло {time}"
    assert custom_cfg["ui"]["text"]["next_prefix_up"] == "Буде приблизно о"
