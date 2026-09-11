import json
import os
import datetime
import structlog
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import sys
import shutil
from dotenv import load_dotenv

from app.reports.common import (
    ALERT_TYPE_RED,
    ALERT_TYPE_YELLOW,
    KYIV_TZ,
    get_alert_color,
    get_alert_intervals as _get_alert_intervals_common,
    merged_alert_duration,
    summarize_alert_intervals,
    sort_alert_intervals_for_render,
)
from app.reports.visual import (
    ALERT_CRITICAL,
    ALERT_WARNING,
    AQI_GOOD,
    AQI_MODERATE,
    AQI_UNHEALTHY,
    HATCH_CLEAR,
    HATCH_LINE_WIDTH,
    HATCH_PLAN,
    HATCH_UNKNOWN,
    PLAN_OUTAGE,
    POWER_DOWN,
    POWER_UP,
    PLAN_ICON,
    REPORT_AQI_STRIP_HEIGHT,
    REPORT_MAIN_STRIP_HEIGHT,
    get_aqi_color,
    get_report_palette,
    style_for_alert_clear,
    style_for_fact,
    style_for_plan,
)

load_dotenv()

# --- Configuration ---
DATA_DIR = os.environ.get("DATA_DIR", "data")


def get_telegram_config():
    from app.config_runtime import get_config

    cfg = get_config()
    return cfg.get("settings", {}).get("telegram_bot_token"), cfg.get(
        "settings", {}
    ).get("telegram_channel_id")


def get_token():
    return get_telegram_config()[0] or os.environ.get("TELEGRAM_BOT_TOKEN")


def get_chat_id():
    return get_telegram_config()[1] or os.environ.get("TELEGRAM_CHANNEL_ID")


logger = structlog.get_logger(__name__)

EVENT_LOG_FILE = os.path.join(DATA_DIR, "event_log.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "last_schedules.json")
HISTORY_FILE = os.path.join(DATA_DIR, "schedule_history.json")
REPORT_ID_FILE = os.path.join(DATA_DIR, "daily_report_id.json")


def get_now():
    now = datetime.datetime.now(KYIV_TZ)
    minutes = now.minute - now.minute % 10
    return now.replace(minute=minutes, second=0, microsecond=0)


def get_quiet_status():
    """Reads current quiet_status from state file."""
    state_file = os.path.join(DATA_DIR, "power_monitor_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
                return state.get("quiet_status", "active")
        except Exception:
            pass
    return "active"


def get_alert_intervals(target_date):
    return _get_alert_intervals_common(target_date, DATA_DIR)


def load_events():
    if not os.path.exists(EVENT_LOG_FILE):
        return []
    try:
        with open(EVENT_LOG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def load_schedule_slots(target_date):
    """
    Returns the list of 48 boolean slots (True=Light, False=Outage) for the target date.
    Checks last_schedules.json first, then schedule_history.json.
    """
    date_str = target_date.strftime("%Y-%m-%d")

    # 1. Try last_schedules.json (current/future)
    if os.path.exists(SCHEDULE_FILE):
        try:
            with open(SCHEDULE_FILE, "r") as f:
                data = json.load(f)

            # Get priority order from config
            from app.light_service import get_config

            cfg = get_config()
            user_priority = (
                cfg.get("advanced", {}).get("data_sources", {}).get("priority", "yasno")
            )
            priority_order = ["yasno", "github"]
            if user_priority in ["yasno", "github"]:
                priority_order = [user_priority] + [
                    s for s in priority_order if s != user_priority
                ]

            # Find the best source with actual slots
            for s_key in priority_order:
                source = data.get(s_key)
                if not source:
                    continue
                group_key = list(source.keys())[0]
                schedule_data = source.get(group_key, {})

                if date_str in schedule_data and schedule_data[date_str].get("slots"):
                    return list(schedule_data[date_str]["slots"])

            # Fallback to merging ONLY if no priority source has slots
            merged_slots = None
            for s_key in ["github", "yasno"]:
                source = data.get(s_key)
                if not source:
                    continue
                group_key = list(source.keys())[0]
                schedule_data = source.get(group_key, {})

                if date_str in schedule_data and schedule_data[date_str].get("slots"):
                    s = schedule_data[date_str]["slots"]
                    if merged_slots is None:
                        merged_slots = list(s)
                    else:
                        for i in range(min(len(merged_slots), len(s))):
                            if s[i] is False:
                                merged_slots[i] = False

            if merged_slots:
                return merged_slots
        except Exception as e:
            logger.error("Error loading schedule", error=str(e))

    # 2. Try schedule_history.json (past)
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
                if date_str in history:
                    res = history[date_str]
                    if isinstance(res, dict):
                        return res.get("slots", [True] * 48)
                    return res
        except Exception as e:
            logger.error("Error loading history", error=str(e))

    # If no schedule found, assume Light (True) for the whole day
    return [True] * 48


def get_intervals_for_date(target_date, events):
    """
    Returns a list of (start_time, end_time, state) for the target date.
    """

    # Target date range
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
        tzinfo=KYIV_TZ
    )
    day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(
        tzinfo=KYIV_TZ
    )

    # If target is today, clip the calculation end to NOW for stats,
    # but the chart X-axis will still cover the full day.
    now = get_now()
    if target_date == now.date():
        calc_end = now
    else:
        calc_end = day_end

    # Sort events by timestamp
    events.sort(key=lambda x: x["timestamp"])

    intervals = []

    # Determine initial state at 00:00
    current_state = "unknown"

    # Find the last event BEFORE the start of the day
    for event in events:
        if event["timestamp"] < day_start.timestamp():
            current_state = event["event"]
        else:
            break

    current_time = day_start

    # Iterate through events strictly within the day
    for event in events:
        event_ts = event["timestamp"]
        event_dt = datetime.datetime.fromtimestamp(event_ts, KYIV_TZ)

        if event_dt < day_start:
            continue
        if event_dt > calc_end:
            break

        # Add interval from current_time to this event
        if current_time < event_dt:
            intervals.append((current_time, event_dt, current_state))

        current_time = event_dt
        current_state = event["event"]

    # Add final interval to end of calculation period
    if current_time < calc_end:
        intervals.append((current_time, calc_end, current_state))

    return intervals


def get_schedule_intervals(target_date, slots):
    """
    Converts 48 boolean slots into time intervals for the chart.
    Returns list of (start_time, duration_hours, is_light)
    """
    if not slots:
        return []

    intervals = []
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
        tzinfo=KYIV_TZ
    )

    current_state = slots[0]
    start_idx = 0

    for i in range(1, 48):
        if slots[i] != current_state:
            # End of block
            end_idx = i

            # Create interval
            start_time = day_start + datetime.timedelta(minutes=start_idx * 30)
            duration = (end_idx - start_idx) * 0.5  # hours
            intervals.append((start_time, duration, current_state))

            # Start new block
            current_state = slots[i]
            start_idx = i

    # Final block
    start_time = day_start + datetime.timedelta(minutes=start_idx * 30)
    duration = (48 - start_idx) * 0.5
    intervals.append((start_time, duration, current_state))

    return intervals


def format_duration(seconds):
    total_minutes = round(seconds / 60)
    h = total_minutes // 60
    m = total_minutes % 60
    parts = []
    if h > 0:
        parts.append(f"{h} г")
    if m > 0:
        parts.append(f"{m} хв")
    return " ".join(parts) if parts else "0 хв"


def generate_chart(
    target_date, intervals, schedule_intervals, alert_intervals, theme="dark", lang="ua"
):
    report_palette = get_report_palette(theme)
    bg_color = report_palette.background
    text_color = report_palette.text
    plt_style = "default" if theme == "light" else "dark_background"

    with plt.style.context(plt_style):
        fig, ax = plt.subplots(figsize=(10, 2.8), facecolor=bg_color)
        ax.set_facecolor(bg_color)

        # Keep incident lanes prominent while making environmental data thinner.
        aqi_y = 9.45
        aqi_h = REPORT_AQI_STRIP_HEIGHT
        alert_y = 11.15
        alert_h = REPORT_MAIN_STRIP_HEIGHT
        sched_y = 13.15
        sched_h = REPORT_MAIN_STRIP_HEIGHT
        act_y = 15.15
        act_h = REPORT_MAIN_STRIP_HEIGHT

        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
            tzinfo=KYIV_TZ
        )
        day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(
            tzinfo=KYIV_TZ
        )

        # --- AQI Data (Bottom Bar) ---
        now = get_now()
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            config_path = "config.json"

        cfg = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            except Exception:
                pass

        aq_cfg = cfg.get("sources", {}).get("air_quality", {})
        lat = aq_cfg.get("lat", "50.408")
        lon = aq_cfg.get("lon", "30.400")

        aqi_intervals = []
        try:
            history_file = os.path.join(DATA_DIR, "metrics_history.json")
            history_data = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r") as f:
                        history_data = json.load(f)
                except Exception:
                    pass

            target_day_metrics = []
            for item in history_data:
                dt_metric = datetime.datetime.fromtimestamp(
                    item.get("timestamp", 0), KYIV_TZ
                )
                if dt_metric.date() == target_date:
                    target_day_metrics.append(item)

            target_day_metrics.sort(key=lambda x: x.get("timestamp", 0))

            if target_day_metrics:
                for idx, item in enumerate(target_day_metrics):
                    ts = item.get("timestamp", 0)
                    aqi_val = item.get("aqi")

                    color = get_aqi_color(aqi_val, unknown_color=report_palette.unknown)

                    start_t = datetime.datetime.fromtimestamp(ts, KYIV_TZ)
                    if start_t > now:
                        continue

                    if idx < len(target_day_metrics) - 1:
                        next_ts = target_day_metrics[idx + 1].get("timestamp", 0)
                        end_t = datetime.datetime.fromtimestamp(
                            min(next_ts, ts + 600), KYIV_TZ
                        )
                    else:
                        end_t = start_t + datetime.timedelta(minutes=10)

                    if end_t > now:
                        end_t = now

                    if end_t > start_t:
                        aqi_intervals.append((start_t, end_t, color))
            else:
                # Fallback to Open-Meteo API if local history is empty
                date_str = target_date.strftime("%Y-%m-%d")
                aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&hourly=us_aqi&timezone=Europe%2FKyiv"
                r_aq = requests.get(aq_url, timeout=15)
                if r_aq.status_code == 200:
                    aq_data = r_aq.json()
                    us_aqi_hourly = aq_data.get("hourly", {}).get("us_aqi", [])

                    for i in range(min(len(us_aqi_hourly), 24)):
                        val = us_aqi_hourly[i]
                        if val is None:
                            continue
                        aqi_val = int(val)

                        color = get_aqi_color(
                            aqi_val, unknown_color=report_palette.unknown
                        )

                        start_t = datetime.datetime.combine(
                            target_date, datetime.time(i, 0)
                        ).replace(tzinfo=KYIV_TZ)
                        if start_t > now:
                            continue
                        end_t = start_t + datetime.timedelta(hours=1)
                        if end_t > now:
                            end_t = now
                        aqi_intervals.append((start_t, end_t, color))
        except Exception as e:
            logger.error("Error fetching daily AQI for chart", error=str(e))

        if not aqi_intervals:
            if target_date <= now.date():
                end_fallback = min(day_end, now)
                if day_start < end_fallback:
                    aqi_intervals = [(day_start, end_fallback, report_palette.unknown)]

        for start, end, color in aqi_intervals:
            start_num = mdates.date2num(start)
            end_num = mdates.date2num(end)
            ax.broken_barh(
                [(start_num, end_num - start_num)],
                (aqi_y, aqi_h),
                facecolors=color,
                edgecolor="none",
            )

        # --- Schedule Data (Middle Bar) ---
        if schedule_intervals:
            for start, duration_hours, is_light in schedule_intervals:
                start_num = mdates.date2num(start)
                duration_days = duration_hours / 24.0
                ax.broken_barh(
                    [(start_num, duration_days)],
                    (sched_y, sched_h),
                    **style_for_plan(is_light, report_palette),
                )

        # --- Alert Data (Middle Bar) ---
        if target_date == now.date():
            alert_end = now
        elif target_date < now.date():
            alert_end = day_end
        else:
            alert_end = day_start

        if day_start < alert_end:
            ax.broken_barh(
                [
                    (
                        mdates.date2num(day_start),
                        mdates.date2num(alert_end) - mdates.date2num(day_start),
                    )
                ],
                (alert_y, alert_h),
                **style_for_alert_clear(report_palette),
            )

        for start, end, alert_type in sort_alert_intervals_for_render(alert_intervals):
            if start > now:
                continue
            if end > now:
                end = now
            start_num = mdates.date2num(start)
            end_num = mdates.date2num(end)
            if end_num > start_num:
                ax.broken_barh(
                    [(start_num, end_num - start_num)],
                    (alert_y, alert_h),
                    facecolors=get_alert_color(alert_type),
                    edgecolor="none",
                )

        # --- Separators ---
        ax.axhline(y=15, color=bg_color, linewidth=0.5, zorder=5)
        ax.axhline(y=13, color=bg_color, linewidth=0.5, zorder=5)
        ax.axhline(y=11, color=bg_color, linewidth=0.5, zorder=5)

        # --- Hour Markers on the Bars (Background Color) ---
        hour_points = []
        for h in range(0, 25):
            point_time = datetime.datetime.combine(
                target_date, datetime.time.min
            ).replace(tzinfo=KYIV_TZ) + datetime.timedelta(hours=h)
            hour_points.append(mdates.date2num(point_time))

        ax.vlines(hour_points, 9.0, 17.0, colors=bg_color, linewidth=0.8, zorder=10)

        # --- Actual Data (Top Bar) ---
        total_up = 0
        total_down = 0

        for start, end, state in intervals:
            duration_sec = (end - start).total_seconds()
            if state == "up":
                total_up += duration_sec
            elif state == "down":
                total_down += duration_sec
            elif state == "unknown":
                total_up += duration_sec

            start_num = mdates.date2num(start)
            end_num = mdates.date2num(end)
            duration_num = end_num - start_num

            ax.broken_barh(
                [(start_num, duration_num)],
                (act_y, act_h),
                **style_for_fact(state, report_palette),
            )

        # --- Formatting ---
        ax.set_ylim(7.5, 18.5)
        ax.set_xlim(mdates.date2num(day_start), mdates.date2num(day_end))

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(text_color)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=KYIV_TZ))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz=KYIV_TZ))
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1, tz=KYIV_TZ))

        ax.tick_params(axis="x", colors=text_color)
        ax.tick_params(axis="y", colors=text_color)

        ax.set_yticks(
            [
                aqi_y + aqi_h / 2,
                alert_y + alert_h / 2,
                sched_y + sched_h / 2,
                act_y + act_h / 2,
            ]
        )
        yticklabels = (
            ["Air", "Alerts", "Schedule", "Actual"]
            if lang == "en"
            else ["Повітря", "Тривоги", "Графік", "Факт"]
        )
        ax.set_yticklabels(yticklabels, color=text_color)

        title_text = (
            f"Electricity Stats for {target_date.strftime('%d.%m.%Y')}"
            if lang == "en"
            else f"Статистика світла за {target_date.strftime('%d.%m.%Y')}"
        )
        ax.set_title(title_text, fontsize=12, color=text_color)

        import matplotlib.patches as mpatches

        if lang == "en":
            fact_up_label = "Power ON"
            fact_down_label = "Power OFF"
            plan_label = "Planned outage"
            clear_label = "No events"
            unknown_label = "Unknown"
            alert_yellow_label = "Yellow warning level"
            alert_red_label = "Red immediate danger"
            aqi_green_label = "AQI: Good"
            aqi_yellow_label = "AQI: Moderate"
            aqi_red_label = "AQI: Unhealthy"
        else:
            fact_up_label = "Світло є"
            fact_down_label = "Світла немає"
            plan_label = "Планове відключення"
            clear_label = "Немає подій"
            unknown_label = "Невідомо"
            alert_yellow_label = "Жовтий рівень"
            alert_red_label = "Червоний рівень"
            aqi_green_label = "AQI: Добре"
            aqi_yellow_label = "AQI: Помірне"
            aqi_red_label = "AQI: Шкідливе"

        fact_up_patch = mpatches.Patch(
            facecolor=POWER_UP, edgecolor=POWER_UP, label=fact_up_label
        )
        fact_down_patch = mpatches.Patch(
            facecolor=POWER_DOWN, edgecolor=POWER_DOWN, label=fact_down_label
        )
        plan_patch = mpatches.Patch(
            facecolor=PLAN_OUTAGE,
            edgecolor=text_color,
            hatch=HATCH_PLAN,
            linewidth=HATCH_LINE_WIDTH,
            label=plan_label,
        )
        clear_patch = mpatches.Patch(
            facecolor=report_palette.track,
            edgecolor=report_palette.unknown,
            hatch=HATCH_CLEAR,
            linewidth=HATCH_LINE_WIDTH,
            label=clear_label,
        )
        unknown_patch = mpatches.Patch(
            facecolor=report_palette.unknown,
            edgecolor=text_color,
            hatch=HATCH_UNKNOWN,
            linewidth=HATCH_LINE_WIDTH,
            label=unknown_label,
        )
        alert_yellow_patch = mpatches.Patch(
            color=ALERT_WARNING, label=alert_yellow_label
        )
        alert_red_patch = mpatches.Patch(color=ALERT_CRITICAL, label=alert_red_label)

        aqi_green = mpatches.Patch(color=AQI_GOOD, label=aqi_green_label)
        aqi_yellow = mpatches.Patch(color=AQI_MODERATE, label=aqi_yellow_label)
        aqi_red = mpatches.Patch(color=AQI_UNHEALTHY, label=aqi_red_label)

        legend = plt.legend(
            handles=[
                fact_up_patch,
                fact_down_patch,
                plan_patch,
                clear_patch,
                unknown_patch,
                alert_yellow_patch,
                alert_red_patch,
                aqi_green,
                aqi_yellow,
                aqi_red,
            ],
            loc="upper center",
            bbox_to_anchor=(0.5, -0.22),
            fancybox=False,
            frameon=False,
            shadow=False,
            ncol=3,
            fontsize="small",
        )
        plt.setp(legend.get_texts(), color=text_color)

        plt.tight_layout()
        plt.subplots_adjust(bottom=0.34)

        suffix = "_light" if theme == "light" else ""
        if lang == "en":
            suffix += "_en"
        filename = os.path.join(
            DATA_DIR, f"report_{target_date.strftime('%Y-%m-%d')}{suffix}.png"
        )
        plt.savefig(filename, dpi=100, facecolor=fig.get_facecolor())
        plt.close()

    return filename, total_up, total_down


def get_last_report_id(target_date):
    if os.path.exists(REPORT_ID_FILE):
        try:
            with open(REPORT_ID_FILE, "r") as f:
                data = json.load(f)
                # Ensure data is a dictionary
                if isinstance(data, dict):
                    date_str = target_date.strftime("%Y-%m-%d")
                    # Backwards compatibility: if old format, check and return
                    if "date" in data and "message_id" in data:
                        if data.get("date") == date_str:
                            return data.get("message_id")
                        else:
                            return None
                    # New format: a mapping of date_str -> message_id
                    return data.get(date_str)
        except Exception:
            pass
    return None


def save_report_id(message_id, target_date):
    data = {}
    if os.path.exists(REPORT_ID_FILE):
        try:
            with open(REPORT_ID_FILE, "r") as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    # Migration: if old format, convert to new format
                    if "date" in loaded_data and "message_id" in loaded_data:
                        old_date = loaded_data["date"]
                        old_id = loaded_data["message_id"]
                        data[old_date] = old_id
                    else:
                        data = loaded_data
        except Exception:
            pass

    date_str = target_date.strftime("%Y-%m-%d")
    data[date_str] = message_id

    # Keep only the last 3 entries to avoid unbounded growth
    if len(data) > 3:
        # Sort by date and keep only the latest 3
        sorted_keys = sorted(data.keys())
        keys_to_remove = sorted_keys[:-3]
        for k in keys_to_remove:
            del data[k]

    try:
        with open(REPORT_ID_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


from app.telegram_client import TelegramClient  # noqa: E402
from app.reports.delivery_state import mark_daily_final_delivered  # noqa: E402
from app.metrics import report_generation_errors  # noqa: E402


def get_telegram_client():
    return TelegramClient(
        get_telegram_config()[0] or os.environ.get("TELEGRAM_BOT_TOKEN"),
        get_telegram_config()[1] or os.environ.get("TELEGRAM_CHANNEL_ID"),
    )


def update_telegram_photo(message_id, photo_path, caption):
    client = get_telegram_client()
    return client.edit_photo(message_id, photo_path, caption) is not None


def delete_telegram_message(message_id):
    client = get_telegram_client()
    return client.delete_message(message_id)


def send_telegram_photo(photo_path, caption, target_date):
    client = get_telegram_client()
    msg_id = client.send_photo(photo_path, caption)
    if msg_id:
        save_report_id(msg_id, target_date)
        logger.info("Report sent successfully.")
    else:
        logger.error("Failed to send report.")
    return msg_id


def build_report_caption(target_date, t_up, t_down, slots, now_time=None):
    if now_time is None:
        now_time = get_now()

    # Terminology: "Monitoring" for today's ongoing day before noon, "Report" for finished days or today after noon.
    is_today = target_date == now_time.date()
    if is_today and now_time.hour < 12:
        title_prefix = "Моніторинг"
    else:
        title_prefix = "Звіт"

    caption = (
        f"📊 <b>{title_prefix} за {target_date.strftime('%d.%m.%Y')}</b>\n\n"
        f"💡 Факт: Світло було: {format_duration(t_up)}\n"
        f"⚡️ Факт: Світла не було: {format_duration(t_down)}"
    )

    alert_intervals = get_alert_intervals(target_date)
    alerts_count = len(alert_intervals)
    if alerts_count > 0:
        alert_summary = summarize_alert_intervals(alert_intervals)
        total_alert_sec = merged_alert_duration(alert_intervals)
        type_parts = []
        for alert_type, label in (
            (ALERT_TYPE_YELLOW, "Жовтий рівень"),
            (ALERT_TYPE_RED, "Червоний рівень"),
        ):
            details = alert_summary[alert_type]
            if details["count"]:
                type_parts.append(
                    f"{label}: {details['count']} ({format_duration(details['duration_sec'])})"
                )
        caption += (
            f"\n🚨 Час тривог без подвійного рахунку: {format_duration(total_alert_sec)}\n"
            f"   • За рівнями (можуть перекриватися): " + "; ".join(type_parts)
        )

    plan_up_sec_formatted = "0 хв"
    diff_hours = 0
    compliance_pct = 0

    if slots:
        plan_up_cnt = sum(1 for s in slots if s)
        plan_up_sec = plan_up_cnt * 1800  # 30 min * 60 sec
        plan_up_sec_formatted = format_duration(plan_up_sec)

        diff_sec = t_up - plan_up_sec
        diff_hours = diff_sec / 3600
        sign = "+" if diff_sec > 0 else "-" if diff_sec < 0 else ""
        _ = f"{sign}{format_duration(abs(diff_sec))}"

        compliance_pct = (t_up / plan_up_sec * 100) if plan_up_sec > 0 else 0

        calc_end_time = (
            now_time
            if is_today
            else datetime.datetime.combine(target_date, datetime.time.max).replace(
                tzinfo=KYIV_TZ
            )
        )
        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
            tzinfo=KYIV_TZ
        )

        plan_up_sec_now = 0
        for i, s in enumerate(slots):
            if s:
                slot_start = day_start + datetime.timedelta(minutes=30 * i)
                slot_end = slot_start + datetime.timedelta(minutes=30)
                if slot_end <= calc_end_time:
                    plan_up_sec_now += 1800
                elif slot_start < calc_end_time:
                    plan_up_sec_now += (calc_end_time - slot_start).total_seconds()

        caption += "\n\n🗓️ <b>План vs Факт:</b>\n"
        caption += f"🗓️ За планом на добу:  {plan_up_sec_formatted}\n"

        compliance_pct_now = (
            (t_up / plan_up_sec_now * 100) if plan_up_sec_now > 0 else 0
        )
        time_label = "На цю хвилину" if is_today else "На кінець доби"
        caption += f"{PLAN_ICON} {time_label}:\n"
        caption += f"💡 Факт {format_duration(t_up)} 🗓️ План {format_duration(plan_up_sec_now)}\n"
        caption += f"👉 Світла {compliance_pct_now:.0f}% від плану\n"
        caption += "---\n"
        caption += f"🕐 Оновлено: {now_time.strftime('%H:%M')}"

    return caption, plan_up_sec_formatted, diff_hours, compliance_pct


if __name__ == "__main__":
    # If called without arguments, calculate target date
    # New logic:
    # 00:00 - 00:09 -> Updates yesterday's report (Final summary at 00:01)
    # 00:10 - 23:59 -> Starts/updates today's report
    now = get_now()

    if now.hour == 0 and now.minute < 10:
        target_date = (now - datetime.timedelta(days=1)).date()
    else:
        target_date = now.date()

    # Simple argument parsing
    for arg in sys.argv[1:]:
        if arg == "--no-send":
            continue
        try:
            target_date = datetime.datetime.strptime(arg, "%Y-%m-%d").date()
        except ValueError:
            pass  # Ignore non-date arguments

    logger.info("Generating report", target_date=target_date)

    events = load_events()
    slots = load_schedule_slots(target_date)

    intervals = get_intervals_for_date(target_date, events)
    sched_intervals = get_schedule_intervals(target_date, slots)
    alert_intervals = get_alert_intervals(target_date)

    if not intervals:
        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(
            tzinfo=KYIV_TZ
        )
        now = get_now()
        calc_end = (
            now
            if target_date == now.date()
            else day_start + datetime.timedelta(hours=24)
        )
        intervals = [(day_start, calc_end, "unknown")]
    # 3. Generate Charts
    filename, t_up, t_down = generate_chart(
        target_date,
        intervals,
        sched_intervals,
        alert_intervals,
        theme="dark",
        lang="ua",
    )
    filename_light, _, _ = generate_chart(
        target_date,
        intervals,
        sched_intervals,
        alert_intervals,
        theme="light",
        lang="ua",
    )
    filename_en, _, _ = generate_chart(
        target_date,
        intervals,
        sched_intervals,
        alert_intervals,
        theme="dark",
        lang="en",
    )
    filename_light_en, _, _ = generate_chart(
        target_date,
        intervals,
        sched_intervals,
        alert_intervals,
        theme="light",
        lang="en",
    )

    # Save copy for Web Dashboard
    web_dir = os.path.join(DATA_DIR, "static")
    if not os.path.exists(web_dir):
        os.makedirs(web_dir)
    shutil.copy(filename, os.path.join(web_dir, "chart.png"))
    shutil.copy(filename_light, os.path.join(web_dir, "chart_light.png"))
    shutil.copy(filename_en, os.path.join(web_dir, "chart_en.png"))
    shutil.copy(filename_light_en, os.path.join(web_dir, "chart_light_en.png"))

    caption, plan_up_sec_formatted, diff_hours, compliance_pct = build_report_caption(
        target_date, t_up, t_down, slots, now
    )

    if slots:
        # Save stats for Web Dashboard
        try:
            stats_data = {
                "plan_up": plan_up_sec_formatted,
                "fact_up": format_duration(t_up),
                "diff": diff_hours,
                "pct": int(compliance_pct),
                "updated_at": get_now().strftime("%H:%M"),
            }
            with open(os.path.join(web_dir, "stats.json"), "w") as f:
                json.dump(stats_data, f)
        except Exception as e:
            logger.error("Error saving stats json", error=str(e))

    is_final = "--final" in sys.argv
    is_cleanup = "--cleanup" in sys.argv
    quiet_status = get_quiet_status()

    def _cleanup_temp_files():
        for f in [filename, filename_light, filename_en, filename_light_en]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass

    if is_cleanup:
        logger.info("Cleanup mode: Removing daily reports from Telegram...")
        # Clean up target_date only (never delete finalized yesterday's summary)
        last_id = get_last_report_id(target_date)
        if last_id:
            logger.info("Deleting report", date=target_date, message_id=last_id)
            delete_telegram_message(last_id)
            save_report_id(None, target_date)
        _cleanup_temp_files()
        sys.exit(0)

    from app.config_runtime import get_config

    cfg = get_config()
    daily_reports_enabled = (
        cfg.get("advanced", {})
        .get("notifications", {})
        .get("telegram_daily_reports", True)
    )

    if "--no-send" in sys.argv:
        logger.info("Telegram sending skipped (--no-send).")
        _cleanup_temp_files()
        sys.exit(0)

    if not daily_reports_enabled:
        logger.info("Telegram daily report is disabled in configuration.")
        _cleanup_temp_files()
        sys.exit(0)

    if is_final:
        # Final daily summary: IGNORE Quiet Mode, send once if enabled
        logger.info("Finalizing daily report", target_date=target_date)
        last_id = get_last_report_id(target_date)
        new_msg_id = send_telegram_photo(filename, caption, target_date)
        if new_msg_id:
            logger.info(
                "Final daily report delivered",
                message_id=new_msg_id,
                target_date=target_date,
            )
            persisted = mark_daily_final_delivered(
                target_date.strftime("%Y-%m-%d"), new_msg_id
            )
            if persisted:
                # Transactional replacement: delete superseded rolling message ONLY after new photo confirmed AND delivery-state persistence succeeds
                if last_id and last_id != new_msg_id:
                    logger.info(
                        "Deleting superseded rolling report message",
                        message_id=last_id,
                    )
                    delete_telegram_message(last_id)
                _cleanup_temp_files()
                sys.exit(0)
            else:
                logger.error(
                    "Failed to persist daily final delivery state. Preserving rolling report for retry eligibility.",
                    target_date=target_date,
                    message_id=new_msg_id,
                )
                report_generation_errors.labels(report_type="daily_final").inc()
                _cleanup_temp_files()
                sys.exit(1)
        else:
            logger.error(
                "Failed to send final daily report to Telegram",
                target_date=target_date,
            )
            report_generation_errors.labels(report_type="daily_final").inc()
            _cleanup_temp_files()
            sys.exit(1)

    # Reactive / live daily update
    if quiet_status == "quiet":
        last_id = get_last_report_id(target_date)
        if last_id:
            logger.info(
                "Quiet mode active, but updating existing report to keep it live",
                message_id=last_id,
            )
            update_telegram_photo(last_id, filename, caption)
        else:
            logger.info("Quiet mode active: Skipping Telegram update (not final).")
        _cleanup_temp_files()
        sys.exit(0)

    # Active mode
    is_all_on_day = False
    if slots and len(slots) >= 48:
        # Check for light outage OR air raid alerts
        alert_intervals = get_alert_intervals(target_date)
        is_all_on_day = (
            all(s is True for s in slots) and (t_down == 0) and not alert_intervals
        )

    last_id = get_last_report_id(target_date)
    if is_all_on_day and not last_id:
        logger.info(
            "Active mode but all-light day: Skipping new graphic report to avoid spam."
        )
        _cleanup_temp_files()
        sys.exit(0)

    if last_id:
        logger.info("Updating existing report", message_id=last_id)
        sent = update_telegram_photo(last_id, filename, caption)
        if not sent:
            logger.info(
                "Update failed (likely message deleted). Sending a NEW message instead..."
            )
            send_telegram_photo(filename, caption, target_date)
    else:
        logger.info("No report ID for today. Sending new report...")
        send_telegram_photo(filename, caption, target_date)

    _cleanup_temp_files()
    sys.exit(0)
