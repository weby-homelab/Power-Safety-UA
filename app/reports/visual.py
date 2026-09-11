import math
from dataclasses import dataclass


# Canonical semantic colors shared by both report renderers and dashboard tests.
POWER_UP = "#14B8A6"
POWER_DOWN = "#F43F5E"
PLAN_OUTAGE = "#818CF8"

ALERT_WARNING = "#F59E0B"
ALERT_CRITICAL = "#EF4444"

AQI_GOOD = "#22C55E"
AQI_MODERATE = "#EAB308"
AQI_UNHEALTHY = "#E11D48"

TRACK_DARK = "#334155"
TRACK_LIGHT = "#CBD5E1"

UNKNOWN_DARK = "#64748B"
UNKNOWN_LIGHT = "#94A3B8"

POWER_UP_ICON = "💡"
POWER_DOWN_ICON = "⚡️"
PLAN_ICON = "🗓️"
ALERT_WARNING_ICON = "⚠️"
ALERT_CRITICAL_ICON = "🚨"
ALERT_CLEAR_ICON = "🛡️"
UNKNOWN_ICON = "❔"

HATCH_PLAN = "////"
HATCH_UNKNOWN = "...."
HATCH_CLEAR = ".."
HATCH_LINE_WIDTH = 1.15

REPORT_MAIN_STRIP_HEIGHT = 1.7
REPORT_AQI_STRIP_HEIGHT = 0.7
WEEKLY_MAIN_STRIP_HEIGHT = 0.36
WEEKLY_AQI_STRIP_HEIGHT = 0.16


@dataclass(frozen=True)
class ReportPalette:
    background: str
    text: str
    track: str
    unknown: str


DARK_REPORT_PALETTE = ReportPalette(
    background="#0F172A",
    text="#F8FAFC",
    track=TRACK_DARK,
    unknown=UNKNOWN_DARK,
)
LIGHT_REPORT_PALETTE = ReportPalette(
    background="#F8FAFC",
    text="#0F172A",
    track=TRACK_LIGHT,
    unknown=UNKNOWN_LIGHT,
)


def get_report_palette(theme: str) -> ReportPalette:
    """Return the report palette while preserving the existing dark default."""
    return LIGHT_REPORT_PALETTE if theme == "light" else DARK_REPORT_PALETTE


def get_aqi_color(value, unknown_color: str = UNKNOWN_DARK) -> str:
    """Map the existing three AQI thresholds to one shared visual token."""
    if value is None or isinstance(value, bool):
        return unknown_color
    try:
        aqi_value = float(value)
    except (TypeError, ValueError):
        return unknown_color
    if not math.isfinite(aqi_value) or aqi_value < 0:
        return unknown_color

    if aqi_value <= 50:
        return AQI_GOOD
    if aqi_value <= 100:
        return AQI_MODERATE
    return AQI_UNHEALTHY


def style_for_fact(state: str, palette: ReportPalette) -> dict[str, object]:
    """Return a non-color-only style for a measured power state."""
    if state == "up":
        return {"facecolors": POWER_UP, "edgecolor": "none"}
    if state == "down":
        return {"facecolors": POWER_DOWN, "edgecolor": "none"}
    return {
        "facecolors": palette.unknown,
        "edgecolor": palette.text,
        "linewidth": HATCH_LINE_WIDTH,
        "hatch": HATCH_UNKNOWN,
    }


def style_for_plan(is_light: object, palette: ReportPalette) -> dict[str, object]:
    """Render normal schedule as a quiet track and outages as a hatched plan."""
    if is_light is True:
        return {
            "facecolors": palette.track,
            "edgecolor": palette.track,
            "linewidth": 0.0,
        }
    if is_light is False:
        return {
            "facecolors": PLAN_OUTAGE,
            "edgecolor": palette.text,
            "linewidth": HATCH_LINE_WIDTH,
            "hatch": HATCH_PLAN,
        }
    return style_for_fact("unknown", palette)


def style_for_alert_clear(palette: ReportPalette) -> dict[str, object]:
    """Use a quiet dotted track for the absence of an alert."""
    return {
        "facecolors": palette.track,
        "edgecolor": palette.unknown,
        "linewidth": HATCH_LINE_WIDTH,
        "hatch": HATCH_CLEAR,
    }
