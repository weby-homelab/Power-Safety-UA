import json
import os
import datetime
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import sys
import shutil
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
DATA_DIR = os.environ.get("DATA_DIR", "data")
def get_telegram_config():
    cfg_path = os.path.join(DATA_DIR, "config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            try:
                cfg = json.load(f)
                return cfg.get("settings", {}).get("telegram_bot_token"), cfg.get("settings", {}).get("telegram_channel_id")
            except: pass
    return None, None

_cfg_token, _cfg_chat = get_telegram_config()
TOKEN = _cfg_token or os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = _cfg_chat or os.environ.get("TELEGRAM_CHANNEL_ID")

if "PYTEST_CURRENT_TEST" in os.environ:
    CHAT_ID = "6313526220"
EVENT_LOG_FILE = os.path.join(DATA_DIR, "event_log.json")
SCHEDULE_FILE = os.path.join(DATA_DIR, "last_schedules.json")
HISTORY_FILE = os.path.join(DATA_DIR, "schedule_history.json")
REPORT_ID_FILE = os.path.join(DATA_DIR, "daily_report_id.json")
def get_timezone():
    try:
        config_path = os.path.join(DATA_DIR, "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
                tz_name = cfg.get("settings", {}).get("timezone", "Europe/Kyiv")
                return ZoneInfo(tz_name)
    except: pass
    return ZoneInfo("Europe/Kyiv")

KYIV_TZ = get_timezone()

DAYS_UA = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]

def get_quiet_status():
    """Reads current quiet_status from state file."""
    state_file = os.path.join(DATA_DIR, "power_monitor_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                return state.get("quiet_status", "active")
        except:
            pass
    return "active"


def get_alert_intervals(target_date):
    log_file = os.path.join(DATA_DIR, "air_raid_log.json")
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            data = json.load(f)
    except Exception:
        return []
    
    intervals = []
    current_start = None
    
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=KYIV_TZ)
    
    # Process events
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
                
    # If alert is still ongoing
    if current_start is not None:
        start = max(current_start, day_start)
        now = datetime.datetime.now(tz=KYIV_TZ)
        end = min(now, day_end)
        if start < end:
            intervals.append((start, end, True))
            
    return intervals


def load_events():
    if not os.path.exists(EVENT_LOG_FILE):
        return []
    try:
        with open(EVENT_LOG_FILE, 'r') as f:
            return json.load(f)
    except:
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
            with open(SCHEDULE_FILE, 'r') as f:
                data = json.load(f)
            
            # Get priority order from config
            from app.light_service import get_config
            cfg = get_config()
            user_priority = cfg.get("advanced", {}).get("data_sources", {}).get("priority", "yasno")
            priority_order = ['yasno', 'github']
            if user_priority in ['yasno', 'github']:
                priority_order = [user_priority] + [s for s in priority_order if s != user_priority]
            
            # Find the best source with actual slots
            for s_key in priority_order:
                source = data.get(s_key)
                if not source: continue
                group_key = list(source.keys())[0]
                schedule_data = source.get(group_key, {})
                
                if date_str in schedule_data and schedule_data[date_str].get('slots'):
                     return list(schedule_data[date_str]['slots'])
            
            # Fallback to merging ONLY if no priority source has slots
            merged_slots = None
            for s_key in ['github', 'yasno']:
                source = data.get(s_key)
                if not source: continue
                group_key = list(source.keys())[0]
                schedule_data = source.get(group_key, {})
                
                if date_str in schedule_data and schedule_data[date_str].get('slots'):
                     s = schedule_data[date_str]['slots']
                     if merged_slots is None:
                         merged_slots = list(s)
                     else:
                         for i in range(min(len(merged_slots), len(s))):
                             if s[i] is False: merged_slots[i] = False
            
            if merged_slots:
                return merged_slots
        except Exception as e:
            print(f"Error loading schedule: {e}")

    # 2. Try schedule_history.json (past)
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
                if date_str in history:
                    res = history[date_str]
                    if isinstance(res, dict):
                        return res.get('slots', [True] * 48)
                    return res
        except Exception as e:
            print(f"Error loading history: {e}")
            
    # If no schedule found, assume Light (True) for the whole day
    return [True] * 48

def get_intervals_for_date(target_date, events):
    """
    Returns a list of (start_time, end_time, state) for the target date.
    """
    
    # Target date range
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=KYIV_TZ)
    
    # If target is today, clip the calculation end to NOW for stats, 
    # but the chart X-axis will still cover the full day.
    now = datetime.datetime.now(KYIV_TZ)
    if target_date == now.date():
        calc_end = now
    else:
        calc_end = day_end

    # Sort events by timestamp
    events.sort(key=lambda x: x['timestamp'])
    
    intervals = []
    
    # Determine initial state at 00:00
    current_state = "unknown"
    
    # Find the last event BEFORE the start of the day
    for event in events:
        if event['timestamp'] < day_start.timestamp():
            current_state = event['event']
        else:
            break
            
    current_time = day_start
    
    # Iterate through events strictly within the day
    for event in events:
        event_ts = event['timestamp']
        event_dt = datetime.datetime.fromtimestamp(event_ts, KYIV_TZ)
        
        if event_dt < day_start:
            continue
        if event_dt > calc_end:
            break
            
        # Add interval from current_time to this event
        if current_time < event_dt:
            intervals.append((current_time, event_dt, current_state))
            
        current_time = event_dt
        current_state = event['event']
        
    # Add final interval to end of calculation period
    if current_time < calc_end:
        intervals.append((current_time, calc_end, current_state))
        
    return intervals

def get_schedule_intervals(target_date, slots):
    """
    Converts 48 boolean slots into time intervals for the chart.
    Returns list of (start_time, duration_hours, is_light)
    """
    if not slots: return []
    
    intervals = []
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    
    current_state = slots[0]
    start_idx = 0
    
    for i in range(1, 48):
        if slots[i] != current_state:
            # End of block
            end_idx = i
            
            # Create interval
            start_time = day_start + datetime.timedelta(minutes=start_idx*30)
            duration = (end_idx - start_idx) * 0.5 # hours
            intervals.append((start_time, duration, current_state))
            
            # Start new block
            current_state = slots[i]
            start_idx = i
            
    # Final block
    start_time = day_start + datetime.timedelta(minutes=start_idx*30)
    duration = (48 - start_idx) * 0.5
    intervals.append((start_time, duration, current_state))
    
    return intervals

def format_duration(seconds):
    total_minutes = round(seconds / 60)
    h = total_minutes // 60
    m = total_minutes % 60
    parts = []
    if h > 0: parts.append(f"{h} г")
    if m > 0: parts.append(f"{m} хв")
    return " ".join(parts) if parts else "0 хв"

def generate_chart(target_date, intervals, schedule_intervals, theme='dark'):
    # Vibrant colors for Fact, Muted for Plan
    if theme == 'dark':
        bg_color = '#0f172a'
        text_color = '#f8fafc'
        fact_on_color = '#14b8a6' # Vibrant Teal
        fact_off_color = '#f43f5e' # Vibrant Rose
        plan_on_color = '#818cf8' # Distinct Indigo
        plan_off_color = '#475569' # Distinct Slate
        plt_style = 'dark_background'
    else:
        bg_color = '#f8fafc'
        text_color = '#0f172a'
        fact_on_color = '#14b8a6'
        fact_off_color = '#f43f5e'
        plan_on_color = '#818cf8'
        plan_off_color = '#64748b'
        plt_style = 'default'

    with plt.style.context(plt_style):
        fig, ax = plt.subplots(figsize=(10, 2.0), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        
        # Define geometries - Glued together
        alert_y = 11.0
        alert_h = 2.0
        sched_y = 13.0
        sched_h = 2.0
        act_y = 15.0
        act_h = 2.0
        
        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
        day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=KYIV_TZ)
        
        # --- Schedule Data (Bottom Bar) ---
        sched_color_map = {True: plan_on_color, False: plan_off_color}
        
        if schedule_intervals:
            for start, duration_hours, is_light in schedule_intervals:
                color = sched_color_map.get(is_light, plan_off_color)
                start_num = mdates.date2num(start)
                duration_days = duration_hours / 24.0
                ax.broken_barh([(start_num, duration_days)], (sched_y, sched_h), facecolors=color, edgecolor='none')

        
        # --- Alert Data (Bottom Bar) ---
        alert_on_color = '#ef4444' # Red for alerts
        alert_off_color = '#334155' if theme == 'dark' else '#cbd5e1'
        ax.broken_barh([(mdates.date2num(day_start), mdates.date2num(day_end) - mdates.date2num(day_start))], (alert_y, alert_h), facecolors=alert_off_color, edgecolor='none')
        alert_intervals = get_alert_intervals(target_date)
        for start, end, is_alert in alert_intervals:
            if is_alert:
                start_num = mdates.date2num(start)
                end_num = mdates.date2num(end)
                ax.broken_barh([(start_num, end_num - start_num)], (alert_y, alert_h), facecolors=alert_on_color, edgecolor='none')
        
        # --- Separators ---
        ax.axhline(y=15, color=bg_color, linewidth=0.5, zorder=5)
        ax.axhline(y=13, color=bg_color, linewidth=0.5, zorder=5)


        # --- Hour Markers on the Bars (Background Color) ---
        hour_points = []
        for h in range(0, 25):
            point_time = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ) + datetime.timedelta(hours=h)
            hour_points.append(mdates.date2num(point_time))
            
        ax.vlines(hour_points, 11.0, 17.0, colors=bg_color, linewidth=0.8, zorder=10)

        # --- Actual Data (Top Bar) ---
        color_map = {'up': fact_on_color, 'down': fact_off_color, 'unknown': fact_on_color}
        
        total_up = 0
        total_down = 0
        
        for start, end, state in intervals:
            duration_sec = (end - start).total_seconds()
            if state == 'up':
                total_up += duration_sec
            elif state == 'down':
                total_down += duration_sec
            elif state == 'unknown':
                total_up += duration_sec
                
            color = color_map.get(state, fact_on_color)
            
            start_num = mdates.date2num(start)
            end_num = mdates.date2num(end)
            duration_num = end_num - start_num
            
            ax.broken_barh([(start_num, duration_num)], (act_y, act_h), facecolors=color, edgecolor='none')

        # --- Formatting ---
        ax.set_ylim(9.5, 18.5) 
        ax.set_xlim(mdates.date2num(day_start), mdates.date2num(day_end))
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color(text_color)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M', tz=KYIV_TZ))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz=KYIV_TZ))
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1, tz=KYIV_TZ))
        
        ax.tick_params(axis='x', colors=text_color)
        ax.tick_params(axis='y', colors=text_color)
        
        ax.set_yticks([alert_y + alert_h/2, sched_y + sched_h/2, act_y + act_h/2])
        ax.set_yticklabels(['Тривоги', 'Графік', 'Факт'], color=text_color)
        
        ax.set_title(f"Статистика світла за {target_date.strftime('%d.%m.%Y')}", fontsize=12, color=text_color)
        
        import matplotlib.patches as mpatches
        green_patch = mpatches.Patch(color=fact_on_color, label=f'Світло є')
        red_patch = mpatches.Patch(color=fact_off_color, label=f'Світла немає')
        yellow_patch = mpatches.Patch(color=plan_on_color, label='Графік: Є')
        gray_patch = mpatches.Patch(color=plan_off_color, label='Графік: Немає')
        
        alert_patch = mpatches.Patch(color='#ef4444', label='Тривога')
        alert_off_patch = mpatches.Patch(color=('#334155' if theme == 'dark' else '#cbd5e1'), label='Немає тривог')


        legend = plt.legend(handles=[green_patch, red_patch, yellow_patch, gray_patch, alert_patch, alert_off_patch],
                   loc='upper center', bbox_to_anchor=(0.5, -0.25),
                   fancybox=False, frameon=False, shadow=False, ncol=3, fontsize='small')
        plt.setp(legend.get_texts(), color=text_color)

        plt.tight_layout()
        plt.subplots_adjust(bottom=0.35)
        
        suffix = "_light" if theme == 'light' else ""
        filename = os.path.join(DATA_DIR, f"report_{target_date.strftime('%Y-%m-%d')}{suffix}.png")
        plt.savefig(filename, dpi=100, facecolor=fig.get_facecolor())
        plt.close()
        
    return filename, total_up, total_down

def get_last_report_id(target_date):
    if os.path.exists(REPORT_ID_FILE):
        try:
            with open(REPORT_ID_FILE, 'r') as f:
                data = json.load(f)
                # Ensure data is a dictionary
                if isinstance(data, dict):
                    date_str = target_date.strftime("%Y-%m-%d")
                    # Backwards compatibility: if old format, check and return
                    if 'date' in data and 'message_id' in data:
                         if data.get('date') == date_str:
                             return data.get('message_id')
                         else:
                             return None
                    # New format: a mapping of date_str -> message_id
                    return data.get(date_str)
        except:
            pass
    return None

def save_report_id(message_id, target_date):
    data = {}
    if os.path.exists(REPORT_ID_FILE):
        try:
            with open(REPORT_ID_FILE, 'r') as f:
                loaded_data = json.load(f)
                if isinstance(loaded_data, dict):
                    # Migration: if old format, convert to new format
                    if 'date' in loaded_data and 'message_id' in loaded_data:
                        old_date = loaded_data['date']
                        old_id = loaded_data['message_id']
                        data[old_date] = old_id
                    else:
                        data = loaded_data
        except:
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
        with open(REPORT_ID_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

from app.storage import StorageUtils
from app.telegram_client import TelegramClient

def get_telegram_client():
    return TelegramClient(TOKEN, CHAT_ID)

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
        print("Report sent successfully.")
    else:
        print("Failed to send report.")

def build_report_caption(target_date, t_up, t_down, slots, now_time=None):
    if now_time is None:
        now_time = datetime.datetime.now(KYIV_TZ)
        
    # Terminology: "Monitoring" for today's ongoing day before noon, "Report" for finished days or today after noon.
    is_today = (target_date == now_time.date())
    if is_today and now_time.hour < 12:
        title_prefix = "Моніторинг"
    else:
        title_prefix = "Звіт"

    caption = (f"📊 <b>{title_prefix} за {target_date.strftime('%d.%m.%Y')}</b>\n\n"
               f"🔆 Світло було: {format_duration(t_up)}\n"
               f"✖️ Світла не було: {format_duration(t_down)}")
               
    alert_intervals = get_alert_intervals(target_date)
    alerts_count = len(alert_intervals)
    if alerts_count > 0:
        total_alert_sec = sum((end - start).total_seconds() for start, end, _ in alert_intervals)
        caption += f"\n⚠️ Повітряні тривоги: {alerts_count} (загалом {format_duration(total_alert_sec)})"

    
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
        diff_formatted = f"{sign}{format_duration(abs(diff_sec))}"
        
        compliance_pct = (t_up / plan_up_sec * 100) if plan_up_sec > 0 else 0
        
        calc_end_time = now_time if is_today else datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=KYIV_TZ)
        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
        
        plan_up_sec_now = 0
        for i, s in enumerate(slots):
            if s:
                slot_start = day_start + datetime.timedelta(minutes=30 * i)
                slot_end = slot_start + datetime.timedelta(minutes=30)
                if slot_end <= calc_end_time:
                    plan_up_sec_now += 1800
                elif slot_start < calc_end_time:
                    plan_up_sec_now += (calc_end_time - slot_start).total_seconds()
        
        caption += f"\n\n📉 <b>План vs Факт:</b>\n"
        caption += f"🔆 За планом на добу:  {plan_up_sec_formatted}\n"
        
        compliance_pct_now = (t_up / plan_up_sec_now * 100) if plan_up_sec_now > 0 else 0
        time_label = "На цю хвилину" if is_today else "На кінець доби"
        caption += f"🔆 {time_label}:\n"
        caption += f"✅ Факт {format_duration(t_up)} ⚡️ План {format_duration(plan_up_sec_now)}\n"
        caption += f"👉 Світла {compliance_pct_now:.0f}% від плану\n"
        caption += f"---\n"
        caption += f"🕐 Оновлено: {now_time.strftime('%H:%M')}"
        
    return caption, plan_up_sec_formatted, diff_hours, compliance_pct

if __name__ == "__main__":
    # If called without arguments, calculate target date
    # New logic: 
    # 00:00 - 00:09 -> Updates yesterday's report (Final summary at 00:01)
    # 00:10 - 23:59 -> Starts/updates today's report
    now = datetime.datetime.now(KYIV_TZ)
    
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
            pass # Ignore non-date arguments
        
    print(f"Generating report for {target_date}...")
    
    events = load_events()
    slots = load_schedule_slots(target_date)
    
    intervals = get_intervals_for_date(target_date, events)
    sched_intervals = get_schedule_intervals(target_date, slots)
    
    if not intervals:
        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
        now = datetime.datetime.now(KYIV_TZ)
        calc_end = now if target_date == now.date() else day_start + datetime.timedelta(hours=24)
        intervals = [(day_start, calc_end, "unknown")]

    filename, t_up, t_down = generate_chart(target_date, intervals, sched_intervals, theme='dark')
    filename_light, _, _ = generate_chart(target_date, intervals, sched_intervals, theme='light')
    
    # Save copy for Web Dashboard
    web_dir = os.path.join(DATA_DIR, "static")
    if not os.path.exists(web_dir): os.makedirs(web_dir)
    shutil.copy(filename, os.path.join(web_dir, "chart.png"))
    shutil.copy(filename_light, os.path.join(web_dir, "chart_light.png"))
    
    caption, plan_up_sec_formatted, diff_hours, compliance_pct = build_report_caption(target_date, t_up, t_down, slots, now)

    if slots:
        # Save stats for Web Dashboard
        try:
            stats_data = {
                "plan_up": plan_up_sec_formatted,
                "fact_up": format_duration(t_up),
                "diff": diff_hours,
                "pct": int(compliance_pct),
                "updated_at": datetime.datetime.now(KYIV_TZ).strftime("%H:%M")
            }
            with open(os.path.join(web_dir, "stats.json"), "w") as f:
                json.dump(stats_data, f)
        except Exception as e:
            print(f"Error saving stats json: {e}")
               
    is_final = "--final" in sys.argv
    is_cleanup = "--cleanup" in sys.argv
    quiet_status = get_quiet_status()

    if is_cleanup:
        print("Cleanup mode: Removing daily reports from Telegram...")
        # Clean up today and yesterday
        yesterday_date = target_date - datetime.timedelta(days=1)
        for d in [target_date, yesterday_date]:
            last_id = get_last_report_id(d)
            if last_id:
                print(f"Deleting report for {d} (ID: {last_id})...")
                delete_telegram_message(last_id)
                save_report_id(None, d)
        sys.exit(0)

    is_all_on_day = False
    if slots and len(slots) >= 48:
        # Check for light outage OR air raid alerts
        alert_intervals = get_alert_intervals(target_date)
        is_all_on_day = all(s is True for s in slots) and (t_down == 0) and not alert_intervals

    if quiet_status == "quiet" and "--no-send" not in sys.argv:
        if is_final:
            print("Quiet mode active. Skipping special text summary as per request.")
            # Delete old message if exists (keeping it clean)
            last_id = get_last_report_id(target_date)
            if last_id:
                print(f"Deleting yesterday's old report message (ID: {last_id}) during quiet finalization...")
                delete_telegram_message(last_id)
        else:
            last_id = get_last_report_id(target_date)
            if last_id:
                print(f"Quiet mode active, but updating existing report (ID: {last_id}) to keep it live...")
                update_telegram_photo(last_id, filename, caption)
            else:
                print("Quiet mode active: Skipping Telegram update (not final).")
        
        if os.path.exists(filename): os.remove(filename)
        if os.path.exists(filename_light): os.remove(filename_light)
        sys.exit(0)

    if is_all_on_day and quiet_status != "quiet" and "--no-send" not in sys.argv:
        last_id = get_last_report_id(target_date)
        if not last_id:
            print("Active mode but all-light day: Skipping new graphic report to avoid spam in Telegram.")
            if os.path.exists(filename): os.remove(filename)
            if os.path.exists(filename_light): os.remove(filename_light)
            sys.exit(0)
        else:
            # If last_id exists, we update it normally (don't delete it). We just let it fall through to the normal logic!
            pass
               
    if "--no-send" not in sys.argv:
        # Check if we can update an existing message
        last_id = get_last_report_id(target_date)
        if last_id and not is_final:
            print(f"Updating existing report (ID: {last_id})...")
            sent = update_telegram_photo(last_id, filename, caption)
            if not sent:
                print("Update failed (likely message deleted). Sending a NEW message instead...")
                send_telegram_photo(filename, caption, target_date)
        else:
            if is_final:
                print(f"Finalizing report for {target_date} as a NEW message...")
                if last_id:
                    print(f"Deleting yesterday's old report message (ID: {last_id})...")
                    delete_telegram_message(last_id)
            else:
                print("No report ID for today. Sending new report...")
            send_telegram_photo(filename, caption, target_date)
    else:
        print("Telegram sending skipped (--no-send).")
    
    if os.path.exists(filename):
        os.remove(filename)
    if os.path.exists(filename_light):
        os.remove(filename_light)
