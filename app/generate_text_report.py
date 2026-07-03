import json
import os
import datetime
from zoneinfo import ZoneInfo
import hashlib
import sys
from dotenv import load_dotenv
from app.generate_daily_report import delete_telegram_message

# Load environment variables
load_dotenv()

# --- Configuration ---
DATA_DIR = os.environ.get("DATA_DIR", "data")


def get_telegram_config():
    cfg_path = os.path.join(DATA_DIR, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            try:
                cfg = json.load(f)
                return cfg.get("settings", {}).get("telegram_bot_token"), cfg.get(
                    "settings", {}
                ).get("telegram_channel_id")
            except Exception:
                pass
    return None, None


_cfg_token, _cfg_chat = get_telegram_config()
TOKEN = _cfg_token or os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = _cfg_chat or os.environ.get("TELEGRAM_CHANNEL_ID")

if "PYTEST_CURRENT_TEST" in os.environ:
    CHAT_ID = "6313526220"
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "last_schedules.json")
TEXT_REPORT_ID_FILE = os.path.join(DATA_DIR, "text_report_id.json")


def get_timezone():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                cfg = json.load(f)
                tz_name = cfg.get("settings", {}).get("timezone", "Europe/Kyiv")
                return ZoneInfo(tz_name)
    except Exception:
        pass
    return ZoneInfo("Europe/Kyiv")


from app.generate_daily_report import KYIV_TZ, DAYS_UA, get_quiet_status  # noqa: E402


def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_slot_time(slot_idx, is_end=False):
    idx = slot_idx % 48
    mins = idx * 30
    h, m = mins // 60, mins % 60
    if h == 0 and m == 0 and is_end and slot_idx > 0:
        return "24:00"
    return f"{h:02d}:{m:02d}"


def get_all_intervals(slots):
    if not slots:
        return []
    intervals = []
    current_state = slots[0]
    start_idx = 0
    for i in range(1, len(slots)):
        if slots[i] != current_state:
            intervals.append(
                {
                    "state": current_state,
                    "start_idx": start_idx,
                    "end_idx": i,
                    "duration": (i - start_idx) * 0.5,
                }
            )
            start_idx = i
            current_state = slots[i]
    intervals.append(
        {
            "state": current_state,
            "start_idx": start_idx,
            "end_idx": len(slots),
            "duration": (len(slots) - start_idx) * 0.5,
        }
    )
    return intervals


def format_duration(hours):
    if hours == int(hours):
        return str(int(hours))
    return f"{hours:g}".replace(".", ",")


def generate_day_block(is_today, intervals, cfg):
    lines = []
    total_on, total_off = 0, 0
    day_start = 0 if is_today else 48
    day_end = 48 if is_today else 96

    day_intervals = []
    for inv in intervals:
        if inv["end_idx"] <= day_start or inv["start_idx"] >= day_end:
            continue

        disp_start = max(inv["start_idx"], day_start)
        disp_end = min(inv["end_idx"], day_end)
        disp_dur = (disp_end - disp_start) * 0.5

        if inv["state"]:
            total_on += disp_dur
        else:
            total_off += disp_dur

        start_str = format_slot_time(disp_start, is_end=False)
        end_str = format_slot_time(disp_end, is_end=True)

        icon = cfg.get("ui", {}).get("icons", {}).get("on", "🔆")
        off_icon = cfg.get("ui", {}).get("icons", {}).get("off", "✖️")
        icon_to_use = icon if inv["state"] else off_icon

        duration_text = f"({format_duration(disp_dur)})"

        line = f"{icon_to_use} {start_str} - {end_str} {duration_text:>5}"
        day_intervals.append(line)

    lines.append("---")
    lines.extend(day_intervals)
    lines.append("---")

    on_icon = cfg.get("ui", {}).get("icons", {}).get("on", "🔆")
    off_icon = cfg.get("ui", {}).get("icons", {}).get("off", "✖️")
    lines.append(f"{on_icon} Світло є: {format_duration(total_on)} год.")
    lines.append(f"{off_icon} Світла нема: {format_duration(total_off)} год.")
    lines.append("---")

    return "\n".join(lines)


def get_report_state():
    if os.path.exists(TEXT_REPORT_ID_FILE):
        try:
            with open(TEXT_REPORT_ID_FILE, "r") as f:
                data = json.load(f)
                return data
        except Exception:
            pass
    return {}


def save_report_state(state):
    with open(TEXT_REPORT_ID_FILE, "w") as f:
        if len(state) > 3:
            sorted_dates = sorted(state.keys())
            state = {k: state[k] for k in sorted_dates[-3:]}
        json.dump(state, f)


def is_all_on(slots):
    if not slots or len(slots) < 48:
        return False
    return all(s is True for s in slots)


def has_actual_outages(target_date_str):
    """Checks if there were any actual 'down' events recorded for the given date."""
    event_log_file = os.path.join(DATA_DIR, "event_log.json")
    if not os.path.exists(event_log_file):
        return False
    try:
        with open(event_log_file, "r") as f:
            events = json.load(f)
            for event in events:
                # event['date_str'] is format "YYYY-MM-DD HH:MM:SS"
                if (
                    event["date_str"].startswith(target_date_str)
                    and event["event"] == "down"
                ):
                    return True
    except Exception:
        pass
    return False


def generate_holiday_report(today_str, tomorrow_str, data, group, icons):
    # Check if today and tomorrow are fully ON
    today_slots = None
    tomorrow_slots = None

    for s_key in ["github", "yasno"]:
        s_data = data.get(s_key, {}).get(group, {})
        if not today_slots:
            today_slots = s_data.get(today_str, {}).get("slots")
        if tomorrow_str and not tomorrow_slots:
            tomorrow_slots = s_data.get(tomorrow_str, {}).get("slots")

    today_all_on = is_all_on(today_slots)
    tomorrow_all_on = is_all_on(tomorrow_slots) if tomorrow_str else False

    if not today_all_on and not tomorrow_all_on:
        return None

    # CRITICAL: If today has actual outages, we cannot claim it's an "all-on" day
    if today_all_on and has_actual_outages(today_str):
        return None

    _ = datetime.datetime.now(KYIV_TZ)
    t_dt = datetime.datetime.strptime(today_str, "%Y-%m-%d")

    header = "Світла смуга триває! 🕊️💡"

    if today_all_on and tomorrow_all_on and tomorrow_str:
        tm_dt = datetime.datetime.strptime(tomorrow_str, "%Y-%m-%d")
        desc = "Сусіди, графіки на сьогодні та завтра нарешті «відпочивають». Маємо повні 48 годин світла без жодних перерв."
        days_info = f"{t_dt.strftime('%d.%m')} ({DAYS_UA[t_dt.weekday()]}): Світло є 24 год. 🔆\n{tm_dt.strftime('%d.%m')} ({DAYS_UA[tm_dt.weekday()]}): Світло є 24 год. 🔆"
    elif today_all_on:
        desc = "Сусіди, графік на сьогодні «відпочиває». Маємо повні 24 години світла без жодних перерв."
        days_info = (
            f"{t_dt.strftime('%d.%m')} ({DAYS_UA[t_dt.weekday()]}): Світло є 24 год. 🔆"
        )
    else:  # only tomorrow
        return None  # Fallback to standard for mixed days if today has outages

    footer = "Дякуємо енергетикам і бажаємо всім максимально продуктивних та яскравих днів! 👋✨"

    full_text = f"<b>{header}</b>\n\n{desc}\n\n{days_info}\n\n{footer}"
    return full_text


def main():
    force_new = "--force-new" in sys.argv
    is_cleanup = "--cleanup" in sys.argv
    now = datetime.datetime.now(KYIV_TZ)
    current_time = now.time()
    current_hour = now.hour

    if is_cleanup:
        print("Cleanup mode: Removing text schedules from Telegram...")
        # Check all possible slots for today and yesterday
        report_state = get_report_state()
        today_str = now.strftime("%Y-%m-%d")
        yesterday_str = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

        for d_str in [today_str, yesterday_str]:
            day_state = report_state.get(d_str, {})
            for slot in ["morning", "evening"]:
                msg_id = day_state.get(f"{slot}_id")
                if msg_id:
                    delete_telegram_message(msg_id)
                    day_state.pop(f"{slot}_id", None)
                    day_state.pop(f"{slot}_hash", None)
            report_state[d_str] = day_state

        save_report_state(report_state)
        return

    if not (datetime.time(0, 10) <= current_time <= datetime.time(23, 45)):
        return

    if get_quiet_status() == "quiet":
        print("Quiet mode active: Skipping text report Telegram update.")
        return

    cfg = load_config()
    if not os.path.exists(SCHEDULE_FILE):
        return
    with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    groups = cfg.get("settings", {}).get("groups", ["GPV36.1"])
    group = groups[0] if groups else "GPV36.1"
    icons = cfg.get("ui", {}).get(
        "icons", {"calendar": "📆", "on": "🔆", "off": "✖️", "clock": "🕐"}
    )

    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    # Calculate if tomorrow data is currently available globally
    has_tomorrow_now = False
    for s_key in ["github", "yasno"]:
        s_tomorrow = (
            data.get(s_key, {}).get(group, {}).get(tomorrow_str, {}).get("slots")
        )
        if s_tomorrow:
            has_tomorrow_now = True
            break

    report_state = get_report_state()
    today_state = report_state.get(today_str, {})

    # Migrate old state format if needed
    if "message_id" in today_state and "morning_id" not in today_state:
        # Convert old format to new format
        today_state = {
            "morning_id": today_state.get("message_id"),
            "morning_hash": today_state.get("hash"),
            "morning_had_tomorrow": has_tomorrow_now,  # Assume current state if migrating
        }

    _ = today_state.get("morning_id")
    evening_id = today_state.get("evening_id")
    _ = today_state.get("morning_had_tomorrow", False)

    target_slot = "morning"
    if evening_id:
        target_slot = "evening"
    elif current_hour >= 20 and has_tomorrow_now:
        target_slot = "evening"

    all_day_contents = []

    days_to_process = [today_str]
    if target_slot == "evening":
        days_to_process.append(tomorrow_str)

    for d_idx, d_str in enumerate(days_to_process):
        is_today = d_str == today_str
        dt = datetime.datetime.strptime(d_str, "%Y-%m-%d")

        source_blocks = []
        has_real_tomorrow_data = False

        for s_key in ["github", "yasno"]:
            s_data = data.get(s_key, {}).get(group, {})
            _ = "ДТЕК" if s_key == "github" else "YASNO"

            combined_slots = []

            s_today = s_data.get(today_str, {}).get("slots")
            s_tomorrow_local = s_data.get(tomorrow_str, {}).get("slots")

            if not is_today and not s_tomorrow_local:
                continue

            if not is_today and s_tomorrow_local:
                has_real_tomorrow_data = True

            if s_today:
                combined_slots.extend(s_today)
                if s_tomorrow_local:
                    combined_slots.extend(s_tomorrow_local)
                else:
                    combined_slots.extend([None] * 48)
            elif not is_today and s_tomorrow_local:
                combined_slots.extend([None] * 48)
                combined_slots.extend(s_tomorrow_local)

            if combined_slots and any(x is not None for x in combined_slots):
                clean_slots = [
                    val if val is not None else (True if i < 48 else False)
                    for i, val in enumerate(combined_slots)
                ]
                intervals = get_all_intervals(clean_slots)
                # Hardcode GitHub as ДТЕК for Telegram display
                source_name = "ДТЕК" if s_key == "github" else "YASNO"
                source_blocks.append(
                    (source_name, generate_day_block(is_today, intervals, cfg))
                )

        if not is_today and not has_real_tomorrow_data:
            continue

        if not source_blocks:
            continue

        day_title = f"{icons.get('calendar', '📆')}  {dt.strftime('%d.%m')} ({DAYS_UA[dt.weekday()]})"
        if len(source_blocks) == 2 and source_blocks[0][1] == source_blocks[1][1]:
            sources_label = f"[{source_blocks[0][0]}, {source_blocks[1][0]}]"
            day_content = f"{day_title}\n{sources_label}\n{source_blocks[0][1]}"
        else:
            blocks = [day_title]
            for name, txt in source_blocks:
                blocks.append(f"[{name}]\n{txt}")
            day_content = "\n".join(blocks)

        all_day_contents.append(day_content)

    if not all_day_contents:
        return

    group_display = group.replace("GPV", "")

    # Try generating a holiday report if today is all-on
    holiday_tomorrow_str = tomorrow_str if target_slot == "evening" else None
    holiday_text = generate_holiday_report(
        today_str, holiday_tomorrow_str, data, group, icons
    )

    # Suppress holiday report if it is just "all-on" spam (as per user request)
    if holiday_text:
        print("Holiday report suppressed to avoid noise.")
        return

    combined_content = "\n\n".join(all_day_contents)
    base_text = f"📈 <b>Графік групи {group_display}</b>\n\n{combined_content}"

    content_hash = hashlib.md5(base_text.encode(), usedforsecurity=False).hexdigest()

    updated_text = cfg.get("ui", {}).get("text", {}).get("updated", "Оновлено")
    footer = f"🕐 {updated_text}: {now.strftime('%H:%M')}"
    full_text = f"{base_text}\n\n{footer}"

    last_id = today_state.get(f"{target_slot}_id") if not force_new else None
    last_hash = today_state.get(f"{target_slot}_hash") if not force_new else None

    from app.telegram_client import TelegramClient

    client = TelegramClient(TOKEN, CHAT_ID)

    if last_id:
        if last_hash != content_hash:
            new_id = client.edit_message(last_id, full_text)
            if new_id:
                today_state[f"{target_slot}_hash"] = content_hash
                if new_id != last_id:
                    today_state[f"{target_slot}_id"] = new_id
                    if target_slot == "morning":
                        today_state["morning_had_tomorrow"] = has_tomorrow_now
                report_state[today_str] = today_state
                save_report_state(report_state)
            else:
                print("Failed to edit text report.")
        else:
            print("Text report hash unchanged. Skipping update.")
    else:
        new_id = client.send_message(full_text, silent=True)
        if new_id:
            today_state[f"{target_slot}_id"] = new_id
            today_state[f"{target_slot}_hash"] = content_hash
            if target_slot == "morning":
                today_state["morning_had_tomorrow"] = has_tomorrow_now
            report_state[today_str] = today_state
            save_report_state(report_state)


if __name__ == "__main__":
    main()
