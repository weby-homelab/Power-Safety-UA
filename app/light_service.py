import http.server
import socketserver
import threading
import time
import json
import asyncio
import aiofiles
from app.models import AppConfig, AppState
import os
import secrets
import datetime
from zoneinfo import ZoneInfo
import requests
from app.telegram_client import TelegramClient
import subprocess
from urllib.parse import urlparse, parse_qs
import sys
import re
import fcntl
import hashlib
from dotenv import load_dotenv

from app.parser_service import update_local_schedules

# Load environment variables
load_dotenv()

# --- Configuration ---
DATA_DIR = os.environ.get("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
def get_config():
    try:
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            config_path = "config.json"
            
        data = StorageUtils.load_json_sync(config_path, default={})
        if data:
            try:
                return AppConfig(**data).model_dump(exclude_unset=False, by_alias=True)
            except Exception as e:
                print(f"Config validation error: {e}")
                return data
    except:
        pass
    return AppConfig().model_dump()

def get_admin_chat_id():
    cfg = get_config()
    return str(cfg.get("settings", {}).get("admin_chat_id", "6313526220"))

def get_safety_net_timeout():
    cfg = get_config()
    return int(cfg.get("settings", {}).get("safety_net_timeout", 35))

def get_push_interval():
    cfg = get_config()
    return int(cfg.get("settings", {}).get("push_interval", 30))

def create_backup(label="manual"):
    """Creates a backup of the current configuration and state."""
    backup_dir = os.path.join(DATA_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now(KYIV_TZ).strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}_{label}.json"
    backup_path = os.path.join(backup_dir, backup_name)
    
    config = get_config()
    # We also include state for safety
    state_copy = StorageUtils.load_json_sync(STATE_FILE, default={})
        
    backup_data = {
        "timestamp": time.time(),
        "date_str": datetime.datetime.now(KYIV_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "label": label,
        "config": config,
        "state": state_copy
    }
    
    StorageUtils.save_json_sync(backup_path, backup_data)
    
    # Cleanup old backups (keep last 10)
    try:
        backups = sorted([f for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".json")])
        if len(backups) > 10:
            for b in backups[:-10]:
                os.remove(os.path.join(backup_dir, b))
    except Exception: pass
    
    return backup_name

def list_backups():
    backup_dir = os.path.join(DATA_DIR, "backups")
    if not os.path.exists(backup_dir): return []
    res = []
    for f in sorted(os.listdir(backup_dir), reverse=True):
        if f.startswith("backup_") and f.endswith(".json"):
            path = os.path.join(backup_dir, f)
            data = StorageUtils.load_json_sync(path)
            if data:
                res.append({
                    "filename": f,
                    "date": data.get("date_str"),
                    "label": data.get("label", "unknown")
                })
    return res

def restore_backup(filename):
    backup_path = os.path.join(DATA_DIR, "backups", filename)
    if not os.path.exists(backup_path): return False, "Backup not found"
    
    try:
        data = StorageUtils.load_json_sync(backup_path)
        if not data: return False, "Failed to load backup"
            
        # 1. Backup current config as "pre_restore" just in case
        create_backup("pre_restore")
        
        # 2. Restore config
        data_dir = os.environ.get("DATA_DIR", ".")
        config_path = os.path.join(data_dir, "config.json")
        StorageUtils.save_json_sync(config_path, data["config"])
            
        # 3. Restore state if available
        if "state" in data:
            StorageUtils.save_json_sync(STATE_FILE, data["state"])
        
        return True, "Success"
    except Exception as e:
        return False, str(e)

def prune_old_data():
    """Removes old events and schedule history based on retention settings."""
    try:
        cfg = get_config()
        retention = cfg.get("advanced", {}).get("retention", {})
        log_days = retention.get("event_log_days", 30)
        sched_days = retention.get("schedule_history_days", 14)
        
        now = time.time()
        
        # 1. Prune event_log.json
        logs = StorageUtils.load_json_sync(EVENT_LOG_FILE, default=None)
        if logs:
            cutoff = now - (log_days * 86400)
            new_logs = [l for l in logs if l.get('timestamp', 0) > cutoff]
            if len(new_logs) < len(logs):
                StorageUtils.save_json_sync(EVENT_LOG_FILE, new_logs)
                print(f"Pruned {len(logs) - len(new_logs)} old events.")

        # 2. Prune schedule_history.json
        history = StorageUtils.load_json_sync(HISTORY_FILE, default=None)
        if history:
            cutoff_date = (datetime.datetime.now(KYIV_TZ) - datetime.timedelta(days=sched_days)).strftime("%Y-%m-%d")
            new_history = {d: v for d, v in history.items() if d >= cutoff_date}
            if len(new_history) < len(history):
                StorageUtils.save_json_sync(HISTORY_FILE, new_history)
                print(f"Pruned {len(history) - len(new_history)} old schedule records.")
    except Exception as e:
        print(f"Error during data pruning: {e}")

def get_advanced_setting(section, key, default=None):
    cfg = get_config()
    val = cfg.get("advanced", {}).get(section, {}).get(key, default)
    if isinstance(default, bool) and isinstance(val, str):
        if val.lower() in ("false", "0", "no"): return False
        if val.lower() in ("true", "1", "yes"): return True
    return val

def get_telegram_token():
    cfg = get_config()
    return cfg.get("settings", {}).get("telegram_bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN")

def get_telegram_channel_id_cfg():
    cfg = get_config()
    return cfg.get("settings", {}).get("telegram_channel_id") or os.environ.get("TELEGRAM_CHANNEL_ID")

TOKEN = get_telegram_token()
CHAT_ID = get_telegram_channel_id_cfg()
ADMIN_CHAT_ID = get_admin_chat_id()

if "PYTEST_CURRENT_TEST" in os.environ:
    CHAT_ID = ADMIN_CHAT_ID
PORT = 8889
# SECRET_KEY handled in state
STATE_FILE = os.path.join(DATA_DIR, "power_monitor_state.json")
STATE_LOCK_FILE = os.path.join(DATA_DIR, "power_monitor_state.lock")
SCHEDULE_FILE = os.path.join(DATA_DIR, "last_schedules.json")

from app.storage import SafeStateContextAsync, StorageUtils
state_mgr = SafeStateContextAsync(STATE_LOCK_FILE)

HISTORY_FILE = os.path.join(DATA_DIR, "schedule_history.json")
EVENT_LOG_FILE = os.path.join(DATA_DIR, "event_log.json")
SCHEDULE_API_URL = os.environ.get("SCHEDULE_API_URL", "")
ALERTS_API_URL = "https://ubilling.net.ua/aerialalerts/"

def get_timezone():
    try:
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            config_path = "config.json"
            
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
                tz_name = cfg.get("settings", {}).get("timezone", "Europe/Kyiv")
                return ZoneInfo(tz_name)
    except:
        pass
    return ZoneInfo("Europe/Kyiv")

KYIV_TZ = get_timezone()

# --- State Management ---
state = {
    "status": "unknown",  # up, down, unknown
    "last_seen": 0,
    "went_down_at": 0,
    "came_up_at": 0,
    "secret_key": None,
    "alert_status": "clear", # clear, active, region
    "quiet_mode": "auto", # auto, forced_on, forced_off
    "quiet_status": "active", # active, quiet
    "pending_confirmation": False,
    "safety_net_pending": False, # New: tracking safety net message
    "safety_net_sent_at": 0,    # New: tracking when safety net was sent
    "safety_net_triggered_for": 0, # New: tracking last_seen to avoid re-triggering
    "muted_until": 0,            # New: for "Technical Failure" mute
    "stability_start": time.time(),
    "admin_token": None,
    "last_schedule_hash": None
}

def trigger_daily_report_update(is_final=False):
    """
    Triggers the generation and update of the daily report chart.
    Runs asynchronously to not block the main thread.
    Uses a lock file to prevent concurrent executions and excessive triggering.
    """
    def run_script():
        lock_file = os.path.join(DATA_DIR, "daily_report.lock")
        try:
            # 1. Check for cooldown/lock
            now = time.time()
            try:
                # Atomic creation of lock file to prevent race conditions
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f:
                    f.write(str(os.getpid()))
            except FileExistsError:
                # If file exists, check if it's stale
                try:
                    mtime = os.path.getmtime(lock_file)
                    if (now - mtime) < 15: return
                    os.utime(lock_file, (now, now))
                except: pass
            
            print(f"Triggering daily report update (is_final={is_final})...")
            # Use absolute paths
            base_dir = os.path.dirname(os.path.abspath(__file__))
            python_exec = sys.executable
            script_path = "-m"; script_name = "app.generate_daily_report"
            
            # Run with --final if requested
            args = [python_exec, script_path]
            if is_final:
                args.append("--final")
            
            args[1] = "-m"; args.insert(2, "app.generate_daily_report"); subprocess.run(args, check=True, cwd=os.path.dirname(base_dir))
            
        except Exception as e:
            print(f"Failed to trigger daily report: {e}")
        finally:
            # Note: We don't necessarily delete the lock file to keep it as a cooldown marker
            pass

    threading.Thread(target=run_script).start()

def trigger_text_report_update():
    """
    Triggers the generation and update of the text schedule report in Telegram.
    """
    def run_script():
        lock_file = os.path.join(DATA_DIR, "text_report.lock")
        try:
            now = time.time()
            try:
                # Atomic creation
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f: f.write(str(os.getpid()))
            except FileExistsError:
                try:
                    if (now - os.path.getmtime(lock_file)) < 15: return
                    os.utime(lock_file, (now, now))
                except: pass
            
            print("Triggering text report update...")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            python_exec = sys.executable
            
            subprocess.run([python_exec, "-m", "app.generate_text_report"], check=True, cwd=os.path.dirname(base_dir))
        except Exception as e:
            print(f"Failed to trigger text report: {e}")

    threading.Thread(target=run_script).start()

def trigger_weekly_report_update():
    """
    Triggers the generation of the weekly report chart for the web.
    """
    def run_script():
        lock_file = os.path.join(DATA_DIR, "weekly_report.lock")
        try:
            now = time.time()
            try:
                # Atomic creation
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, 'w') as f: f.write(str(os.getpid()))
            except FileExistsError:
                try:
                    if (now - os.path.getmtime(lock_file)) < 15: return
                    os.utime(lock_file, (now, now))
                except: pass
            
            print("Triggering weekly report update...")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            python_exec = sys.executable
            
            output_path = os.path.join(DATA_DIR, "static", "weekly.png")
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            subprocess.run([python_exec, "-m", "app.generate_weekly_report", "--output", output_path], check=True, cwd=os.path.dirname(base_dir))
        except Exception as e:
            print(f"Failed to trigger weekly report: {e}")

    threading.Thread(target=run_script).start()

async def log_event(event_type, timestamp):
    """
    Logs an event (up/down) to a JSON file for historical analysis.
    """
    try:
        entry = {
            "timestamp": timestamp,
            "event": event_type,
            "date_str": datetime.datetime.fromtimestamp(timestamp, KYIV_TZ).strftime("%Y-%m-%d %H:%M:%S")
        }
        
        async with state_mgr:
            logs = await StorageUtils.load_json_async(EVENT_LOG_FILE, default=[])
            if not isinstance(logs, list): logs = []
            
            logs.append(entry)
            if len(logs) > 1000: 
                logs = logs[-1000:]
                
            await StorageUtils.save_json_async(EVENT_LOG_FILE, logs)
            
    except Exception as e:
        print(f"Failed to log event: {e}")

    # Immediately trigger report updates to reflect live status
    trigger_daily_report_update()
    trigger_weekly_report_update()

async def load_state():
    global state
    async with state_mgr:
        saved_state = await StorageUtils.load_json_async(STATE_FILE, default={})
        if not saved_state:
            print(f"Warning: load_state loaded empty state from {STATE_FILE}. Status will be unknown.")
            
        if saved_state:
            state.update(saved_state)
            
        try:
            validated_state = AppState(**state).model_dump(exclude_unset=False)
            state.update(validated_state)
        except Exception as e:
            print(f"State validation error: {e}")

    if not state.get("secret_key"):
        state["secret_key"] = os.environ.get("SECRET_KEY", secrets.token_urlsafe(16))

    if not state.get("admin_token"):
        async with state_mgr:
            state["admin_token"] = secrets.token_urlsafe(16)
            await save_state()

async def save_state():
    async with state_mgr:
        await StorageUtils.save_json_async(STATE_FILE, state)

def get_current_time():
    # Returns local time timestamp
    return time.time()

def format_duration(seconds, lang='ua'):
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    m = int((seconds % 3600) // 60)
    parts = []
    if lang == 'en':
        if d > 0:
            parts.append(f"{d}d")
            if h > 0: parts.append(f"{h}h")
        else:
            if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")
        return " ".join(parts) if parts else "0m"
    else:
        if d > 0:
            parts.append(f"{d}д")
            if h > 0: parts.append(f"{h} год")
        else:
            if h > 0: parts.append(f"{h} г")
        if m > 0: parts.append(f"{m} хв")
        return " ".join(parts) if parts else "0 хв"

def get_best_source_internal(data, date_str):
    """Internal helper to find source with slots or fallback to emergency."""
    cfg = get_config()
    priority_order = ['yasno', 'github']
    user_priority = cfg.get("advanced", {}).get("data_sources", {}).get("priority", "yasno")
    
    if user_priority in ['yasno', 'github']:
        priority_order = [user_priority] + [s for s in priority_order if s != user_priority]
    elif user_priority == 'custom':
        priority_order = ['custom', 'yasno', 'github']

    # 1. First Pass: Try to find any source with actual slots (following priority)
    for s_name in priority_order:
        src = data.get(s_name)
        if not src: continue
        group_keys = list(src.keys())
        if not group_keys: continue
        group_key = group_keys[0]
        day_data = src[group_key].get(date_str)
        if day_data and day_data.get('slots'):
            # Use this source. is_emergency is True ONLY if THIS source says so.
            return src, (day_data.get('status') == 'emergency')

    # 2. Second Pass: If no slots found, find any source with emergency status
    for s_name in priority_order:
        src = data.get(s_name)
        if not src: continue
        group_keys = list(src.keys())
        if not group_keys: continue
        group_key = group_keys[0]
        day_data = src[group_key].get(date_str)
        if day_data and day_data.get('status') == 'emergency':
            return src, True
            
    return None, False

def get_next_scheduled_event(event_time, look_for_light):
    """
    Finds the next scheduled transition to the target state.
    look_for_light: True if looking for next ON, False for next OFF.
    """
    try:
        if not os.path.exists(SCHEDULE_FILE): return None
        with open(SCHEDULE_FILE, 'r') as f: data = json.load(f)
        
        now_dt = datetime.datetime.fromtimestamp(event_time, KYIV_TZ)
        today_str = now_dt.strftime("%Y-%m-%d")
        tomorrow_str = (now_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        source, is_emergency = get_best_source_internal(data, today_str)
        if not source: return None
        
        group_key = list(source.keys())[0]
        schedule_data = source[group_key]
        
        if today_str not in schedule_data or not schedule_data[today_str].get('slots'):
            return None
        
        # Build 48-hour slot list
        slots = list(schedule_data[today_str]['slots'])
        tomorrow_data = schedule_data.get(tomorrow_str)
        if tomorrow_data and isinstance(tomorrow_data, dict) and tomorrow_data.get('slots'):
            slots.extend(tomorrow_data['slots'])
        else:
            slots.extend([slots[-1]] * 48)
            
        current_slot_idx = (now_dt.hour * 2) + (1 if now_dt.minute >= 30 else 0)
        
        target_idx = -1
        
        # Search for transition (prefer point where it *starts* being look_for_light)
        for i in range(current_slot_idx + 1, len(slots)):
            if slots[i] == look_for_light:
                # If we are currently in that state according to schedule, we look for NEXT block
                if i > 0 and slots[i-1] != look_for_light:
                    target_idx = i
                    break
        
        # Fallback search
        if target_idx == -1:
            if slots[current_slot_idx] != look_for_light:
                for i in range(current_slot_idx + 1, len(slots)):
                    if slots[i] == look_for_light:
                        target_idx = i
                        break
                    
        if target_idx == -1: return None
        
        # Find end of that block
        end_idx = len(slots)
        for i in range(target_idx + 1, len(slots)):
            if slots[i] != look_for_light:
                end_idx = i
                break
                
        def idx_to_hm(idx):
            rem = idx % 48
            h = rem // 2
            m = 30 if rem % 2 else 0
            return f"{h:02d}:{m:02d}"
            
        start_t = idx_to_hm(target_idx)
        end_t = idx_to_hm(end_idx)
        
        # Calculate time until start_t
        days_offset = target_idx // 48
        rem_idx = target_idx % 48
        
        target_dt = now_dt.replace(hour=rem_idx // 2, minute=(30 if rem_idx % 2 else 0), second=0, microsecond=0)
        if days_offset > 0: target_dt += datetime.timedelta(days=days_offset)
        
        diff_sec = (target_dt - now_dt).total_seconds()
        if diff_sec < 0: diff_sec = 0
        
        return {
            "time_left_sec": diff_sec,
            "interval": f"{start_t}-{end_t}"
        }
    except Exception as e:
        print(f"Error in get_next_scheduled_event: {e}")
        return None

def format_event_message(is_up, event_time, prev_event_time):
    time_str = datetime.datetime.fromtimestamp(event_time, KYIV_TZ).strftime("%H:%M")
    cfg = get_config()
    txt = cfg.get("ui", {}).get("text", {})
    
    if is_up:
        header = txt.get("event_up", "🟢 <b>{time} Світло з'явилося</b>").format(time=time_str)
        duration_prefix = txt.get("dur_prefix_up", "Не було")
        wait_prefix = txt.get("next_prefix_down", "❌ Вимкнення через")
        look_for_light = False # Next we wait for OFF
    else:
        header = txt.get("event_down", "🔴 <b>{time} Світло зникло</b>").format(time=time_str)
        duration_prefix = txt.get("dur_prefix_down", "Воно було")
        wait_prefix = txt.get("next_prefix_up", "💡 Очікуємо через")
        look_for_light = True # Next we wait for ON

    # 1. Deviation
    dev_msg = get_deviation_info(event_time, is_up)
    dev_line = ""
    if dev_msg:
        m = re.search(r"(?:Увімкнули|Вимкнули)\s+(раніше|пізніше)\s+на\s+(.+)$", dev_msg)
        if m:
            timing = m.group(1)
            value = m.group(2)
            dev_line = txt.get("dev_shift", "⚡️ На {value} {timing} графіка").format(value=value, timing=timing)
        elif "точно за графіком" in dev_msg:
            dev_line = txt.get("dev_exact", "⚡️ Точно за графіком")

    # 2. Previous Duration
    if prev_event_time > 0:
        dur_sec = abs(event_time - prev_event_time)
        dur_str = format_duration(dur_sec)
    else:
        dur_str = "невідомо"
    dur_line = f"🕓 {duration_prefix} {dur_str}"
    
    # 3. Next event and Interval
    next_info = get_next_scheduled_event(event_time, look_for_light)
    wait_line = ""
    interval_line = ""
    if next_info:
        wait_sec = next_info["time_left_sec"]
        if wait_sec < 60:
            wait_dur = "менше хвилини"
        else:
            wait_dur = format_duration(wait_sec)
        
        wait_line = f"{wait_prefix} ~ {wait_dur}"
        interval_line = f"🗓 ({next_info['interval']})"
    else:
        if is_up:
            wait_line = "❌ Відключення не плануються 🔆"
        else:
            wait_line = f"{wait_prefix} невідомий час 🤷‍♂️"

    msg = f"{header}\n"
    if dev_line: msg += f"{dev_line}\n"
    msg += f"{dur_line}\n"
    
    msg += f"{wait_line}"
    if interval_line:
        msg += f",\n{interval_line}"
    
    return msg.strip()

def get_schedule_context(lang='ua'):
    try:
        with open(SCHEDULE_FILE, 'r') as f:
            data = json.load(f)
        
        now = datetime.datetime.now(KYIV_TZ)
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        source, is_emergency = get_best_source_internal(data, today_str)
        if not source:
            return (None, None, "Unknown" if lang == 'en' else "Невідомо", None, False)
        
        group_key = list(source.keys())[0]
        schedule_data = source[group_key]
        
        if today_str not in schedule_data or not schedule_data[today_str].get('slots'):
            if is_emergency:
                return (None, None, "⚠️ Emergency outages" if lang == 'en' else "⚠️ Екстрені відключення", None, True)
            return (None, None, "No schedule" if lang == 'en' else "Графік відсутній", None, False)
            
        slots = list(schedule_data[today_str]['slots'])
        has_tomorrow = False
        if tomorrow_str in schedule_data and schedule_data[tomorrow_str].get('slots'):
            slots.extend(schedule_data[tomorrow_str]['slots'])
            has_tomorrow = True
        else:
            slots.extend([slots[-1]] * 48)
            
        current_slot_idx = (now.hour * 2) + (1 if now.minute >= 30 else 0)
        is_light_now = slots[current_slot_idx]
        
        end_idx = len(slots)
        for i in range(current_slot_idx + 1, len(slots)):
            if slots[i] != is_light_now:
                end_idx = i
                break
        
        def format_idx_to_time(idx):
            if idx >= 96:
                if lang == 'en':
                    return "no outages scheduled 🔆" if has_tomorrow else "unknown time 🤷‍♂️"
                else:
                    return "відключення не плануються 🔆" if has_tomorrow else "невідомий час 🤷‍♂️"
            day_offset = idx // 48
            rem_idx = idx % 48
            h = rem_idx // 2
            m = 30 if rem_idx % 2 else 0
            if day_offset == 0: return f"{h:02d}:{m:02d}"
            elif day_offset == 1:
                if h == 0 and m == 0: return "24:00"
                if lang == 'en':
                    return f"tomorrow at {h:02d}:{m:02d}"
                else:
                    return f"завтра о {h:02d}:{m:02d}"
            return "day after tomorrow" if lang == 'en' else "післязавтра"

        t_end = format_idx_to_time(end_idx)
        next_start_idx = end_idx
        next_duration = None
        
        if next_start_idx < len(slots):
            if next_start_idx >= 48 and not has_tomorrow:
                next_range = "unknown time 🤷‍♂️" if lang == 'en' else "невідомий час 🤷‍♂️"
            else:
                next_end_idx = len(slots)
                for i in range(next_start_idx + 1, len(slots)):
                    if slots[i] == is_light_now:
                        next_end_idx = i
                        break
                ns_t = format_idx_to_time(next_start_idx)
                ne_t = format_idx_to_time(next_end_idx)
                
                if next_start_idx >= 96 or (next_start_idx >= 48 and next_end_idx >= 96 and is_light_now):
                    if lang == 'en':
                        next_range = "no outages scheduled 🔆" if has_tomorrow else "unknown time 🤷‍♂️"
                    else:
                        next_range = "відключення не плануються 🔆" if has_tomorrow else "невідомий час 🤷‍♂️"
                else:
                    next_range = f"{ns_t} - {ne_t}"
                     
                dur_h = (next_end_idx - next_start_idx) * 0.5
                next_duration = f"{dur_h:g}"
                if lang == 'ua':
                    next_duration = next_duration.replace('.', ',')
        else:
            if lang == 'en':
                next_range = "no outages scheduled 🔆" if has_tomorrow else "unknown time 🤷‍♂️"
            else:
                next_range = "відключення не плануються 🔆" if has_tomorrow else "невідомий час 🤷‍♂️"
            
        return (is_light_now, t_end, next_range, next_duration, is_emergency)
    except Exception as e:
        print(f"Schedule error: {e}")
        return (None, None, "Error" if lang == 'en' else "Помилка", None, False)

def send_telegram(message):
    token = get_telegram_token()
    chat_id = get_admin_chat_id() if "PYTEST_CURRENT_TEST" in os.environ else get_telegram_channel_id_cfg()
    if not token or not chat_id:
        print("Telegram configuration missing (TOKEN or CHAT_ID)")
        return
    token_masked = token[:5] + "..." + token[-5:]
    print(f"DEBUG: Sending telegram message to {chat_id} via bot {token_masked}")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code != 200:
            err_msg = r.text.replace(token, "[REDACTED_TOKEN]")
            print(f"Telegram API Error (Status {r.status_code}): {err_msg}")
    except Exception as e:
        err_str = str(e).replace(token, "[REDACTED_TOKEN]")
        print(f"Failed to send Telegram message: {err_str}")

def send_admin_confirmation(timestamp):
    token = get_telegram_token()
    msg = "⚠️ Зафіксовано втрату зв'язку! Режим 'Інформаційний спокій' активний. Це вимкнення світла чи збій обладнання?"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": get_admin_chat_id(),
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[{"text": "🔴 Світло зникло", "callback_data": f"confirm_down_{timestamp}"},
                                 {"text": "🟢 Збій / Роботи", "callback_data": f"ignore_down_{timestamp}"}]]
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send admin confirmation: {e}")

def send_safety_net_admin(timestamp):
    token = get_telegram_token()
    msg = "🚨 <b>SAFETY NET: ВТРАТА ПУША!</b>\n\nВже 35 сек немає зв'язку. Що сталося?"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": get_admin_chat_id(),
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [{"text": "🔴 Світло зникло?", "callback_data": f"sn_down_{timestamp}"},
                 {"text": "🛠 Технічний збій?", "callback_data": f"sn_tech_{timestamp}"}],
                [{"text": "🤷‍♂️ Не знаю!", "callback_data": f"sn_dontknow_{timestamp}"}]
            ]
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send safety net admin: {e}")

def get_deviation_info(event_time, is_up, lang='ua'):
    try:
        if not os.path.exists(SCHEDULE_FILE): return ""
        with open(SCHEDULE_FILE, 'r') as f: data = json.load(f)
        dt = datetime.datetime.fromtimestamp(event_time, KYIV_TZ)
        date_str = dt.strftime("%Y-%m-%d")
        source, is_emergency = get_best_source_internal(data, date_str)
        if not source: return ""
        group_key = list(source.keys())[0]
        schedule_data = source[group_key]
        if date_str not in schedule_data or not schedule_data[date_str].get('slots'):
            return ""
        slots = schedule_data[date_str]['slots']
        best_diff = 9999
        for i in range(49):
            state_before = slots[i-1] if i > 0 else (not slots[0])
            state_after = slots[i] if i < 48 else slots[47] 
            if state_before != state_after:
                transition_type = 'up' if (not state_before and state_after) else 'down'
                expected_type = 'up' if is_up else 'down'
                if transition_type == expected_type:
                    trans_h, trans_m = i // 2, (30 if i % 2 else 0)
                    trans_dt = dt.replace(hour=trans_h, minute=trans_m, second=0, microsecond=0)
                    diff = (dt - trans_dt).total_seconds() / 60
                    if abs(diff) < abs(best_diff): best_diff = int(diff)
        if abs(best_diff) > 180: return ""
        abs_diff = abs(best_diff)
        h, m = abs_diff // 60, abs_diff % 60
        dur_parts = []
        if lang == 'en':
            if h > 0: dur_parts.append(f"{h}h")
            if m > 0: dur_parts.append(f"{m}m")
            dur_str = " ".join(dur_parts) if dur_parts else "0m"
            action = "Powered ON" if is_up else "Powered OFF"
            timing = "later" if best_diff > 0 else "earlier"
            if best_diff == 0: return f"• {action} strictly on schedule"
            return f"• {action} {timing} by {dur_str}"
        else:
            if h > 0: dur_parts.append(f"{h} год")
            if m > 0: dur_parts.append(f"{m} хв")
            dur_str = " ".join(dur_parts) if dur_parts else "0 хв"
            action = "Увімкнули" if is_up else "Вимкнули"
            timing = "пізніше" if best_diff > 0 else "раніше"
            if best_diff == 0: return f"• {action} точно за графіком"
            return f"• {action} {timing} на {dur_str}"
    except Exception as e:
        print(f"Error in deviation calc: {e}")
        return ""

def get_nearest_schedule_switch(event_time, target_is_up):
    try:
        if not os.path.exists(SCHEDULE_FILE): return None
        with open(SCHEDULE_FILE, 'r') as f: data = json.load(f)
        dt = datetime.datetime.fromtimestamp(event_time, KYIV_TZ)
        date_str = dt.strftime("%Y-%m-%d")
        source, is_emergency = get_best_source_internal(data, date_str)
        if not source: return None
        group_key = list(source.keys())[0]
        schedule_data = source[group_key]
        if date_str not in schedule_data or not schedule_data[date_str].get('slots'):
            return None
        slots = schedule_data[date_str]['slots']
        best_diff = 9999
        best_time_str = None
        for i in range(49):
            state_before = slots[i-1] if i > 0 else slots[0]
            state_after = slots[i] if i < 48 else slots[47]
            if i == 0: state_before = not state_after
            if state_before != state_after:
                if state_after == target_is_up:
                    trans_h, trans_m = i // 2, (30 if i % 2 else 0)
                    trans_dt = dt.replace(hour=trans_h, minute=trans_m, second=0, microsecond=0)
                    diff = abs((dt - trans_dt).total_seconds())
                    if diff < best_diff:
                        best_diff = diff
                        best_time_str = f"{trans_h:02d}:{trans_m:02d}"
        if best_diff > 10800: return None
        return best_time_str
    except:
        return None

def get_air_raid_alert():
    try:
        r = requests.get(ALERTS_API_URL, timeout=5)
        if r.status_code == 200:
            data = r.json()
            alerts = data.get("states", {})
            is_alert_city = "м. Київ" in alerts and alerts["м. Київ"].get("alertnow", False)
            is_alert_region = "Київська область" in alerts and alerts["Київська область"].get("alertnow", False)
            status_text = "active" if is_alert_city else ("region" if is_alert_region else "clear")
            location = "м. Київ" if is_alert_city else ("Київська область" if is_alert_region else "Тривоги немає")
            return {"city": is_alert_city, "region": is_alert_region, "status": status_text, "location": location}
    except Exception as e:
        print(f"Error fetching alerts: {e}")
    return {"status": "unknown", "location": "Невідомо"}

async def update_quiet_status():
    async with state_mgr:
        q_mode = state.get("quiet_mode", "auto")
        old_status = state.get("quiet_status", "active")
        is_eligible = check_quiet_mode_eligibility()
        new_status = "quiet" if q_mode == "forced_on" else ("active" if q_mode == "forced_off" else ("quiet" if is_eligible else "active"))
        if new_status != old_status:
            state["quiet_status"] = new_status
            if new_status == "quiet":
                state["stability_start"] = time.time()
                # CLEANUP: When entering quiet mode, remove active reports from channel
                print("Entering Quiet Mode. Cleaning up active reports...")
                def run_cleanup():
                    try:
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        python_exec = sys.executable
                        subprocess.run([python_exec, "-m", "app.generate_daily_report", "--cleanup"], cwd=os.path.dirname(base_dir))
                        subprocess.run([python_exec, "-m", "app.generate_text_report", "--cleanup"], cwd=os.path.dirname(base_dir))
                    except Exception: pass
                threading.Thread(target=run_cleanup).start()
            else:
                def trigger_report():
                    try:
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        python_exec = sys.executable
                        
                        time.sleep(2)
                        subprocess.run([python_exec, "-m", "app.generate_text_report", "--force-new"], check=True, cwd=os.path.dirname(base_dir))
                    except Exception as e:
                        print(f"Failed to trigger text report: {e}")
                threading.Thread(target=trigger_report).start()
            await save_state()
            print(f"Quiet mode status updated to: {new_status}")

async def _check_safety_net_trigger(current_time, last_seen):
    safety_net_timeout = get_safety_net_timeout()
    if (current_time - last_seen) > safety_net_timeout and \
       not state.get("safety_net_pending") and state.get("safety_net_triggered_for") != last_seen:
        if (current_time - last_seen) < 180:
            state["safety_net_pending"] = True
            state["safety_net_sent_at"] = current_time
            state["safety_net_triggered_for"] = last_seen
            await save_state()
            threading.Thread(target=send_safety_net_admin, args=(current_time,)).start()

async def _check_safety_net_timeout(current_time):
    sent_at = state.get("safety_net_sent_at", 0)
    if state.get("safety_net_pending") and (current_time - sent_at) > 180:
        state["safety_net_pending"] = False
        await save_state()

async def _check_outage_detection(current_time, last_seen):
    if (current_time - last_seen) > 180:
        state["status"] = "down"
        state["safety_net_pending"] = False
        down_time_ts = last_seen + get_push_interval()
        state["went_down_at"] = down_time_ts
        await log_event("down", down_time_ts)
        msg = format_event_message(False, down_time_ts, state.get("came_up_at", 0))
        if state.get('quiet_status') == 'quiet':
            state['pending_confirmation'] = True
            threading.Thread(target=send_admin_confirmation, args=(down_time_ts,)).start()
        else:
            threading.Thread(target=send_telegram, args=(msg,)).start()
        await save_state()

async def _check_auto_confirmation(current_time):
    if state.get('pending_confirmation') and (current_time - state.get('went_down_at', 0)) > 300:
        cfg = get_config()
        quiet_config = cfg.get("advanced", {}).get("quiet_mode", {})
        auto_confirm = quiet_config.get("auto_confirm", True)
        
        q_mode = state.get("quiet_mode", "auto")
        
        if q_mode == "forced_on":
            print("Safety Net timeout: Quiet Mode is FORCED ON. Bypassing public alarm.")
            state['pending_confirmation'] = False
            await save_state()
            return
            
        if q_mode == "auto" and state.get("quiet_status") == "quiet":
            print("Safety Net timeout: AUTO Quiet Mode is active. Bypassing public alarm to maintain silence.")
            state['pending_confirmation'] = False
            await save_state()
            return
            
        if not auto_confirm:
            print("Safety Net timeout: auto_confirm is Disabled. Bypassing public alarm.")
            state['pending_confirmation'] = False
            await save_state()
            return

        print("Safety Net timeout: Admin did not respond in 5 mins. Assuming real outage. Sending public alarm.")
        state['pending_confirmation'] = False
        state['quiet_status'] = 'active'
        
        down_time = state.get('went_down_at', 0)
        msg = format_event_message(False, down_time, state.get("came_up_at", 0))
        threading.Thread(target=send_telegram, args=(msg,)).start()
        
        await save_state()

async def monitor_loop():
    print("Monitor loop started...")
    while True:
        try:
            await asyncio.sleep(5)
            await load_state()
            async with state_mgr:
                current_time = get_current_time()
                last_seen = state["last_seen"]
                
                if state.get("muted_until", 0) > current_time: 
                    continue
                    
                if state["status"] == "up":
                    await _check_safety_net_trigger(current_time, last_seen)
                    await _check_safety_net_timeout(current_time)
                    await _check_outage_detection(current_time, last_seen)

                await _check_auto_confirmation(current_time)
                
        except Exception as e:
            print(f"Critical error in monitor_loop: {e}")
            await asyncio.sleep(5)


async def alerts_loop():
    print("Alerts loop started...")
    while True:
        try:
            current_alert = get_air_raid_alert()
            new_status = current_alert.get("status")
            if new_status != "unknown":
                await load_state()
                async with state_mgr:
                    old_status = state.get("alert_status", "clear")
                    if new_status != old_status:
                        now_dt = datetime.datetime.now(KYIV_TZ)
                        time_str = now_dt.strftime("%H:%M")
                        
                        # Check config for air raid notifications
                        cfg = get_config()
                        can_notify = cfg.get("advanced", {}).get("notifications", {}).get("telegram_air_raid_alerts", True)
                        if str(can_notify).lower() in ("false", "0", "no"):
                            can_notify = False
                        else:
                            can_notify = bool(can_notify)

                        if new_status == "active":
                            state["alert_start_time"] = now_dt.timestamp()

                            try:
                                log_path = os.path.join(DATA_DIR, "air_raid_log.json")
                                l_data = json.load(open(log_path)) if os.path.exists(log_path) else []
                                # Only add if not already active or log is empty
                                if not l_data or l_data[-1].get("event") != "active":
                                    l_data.append({"timestamp": now_dt.timestamp(), "event": "active"})
                                    json.dump(l_data, open(log_path, "w"), indent=2)
                            except: pass

                            if can_notify:
                                msg = f"⚠️ <b>{time_str} ПОВІТРЯНА ТРИВОГА! КИЇВ</b>"
                                threading.Thread(target=send_telegram, args=(msg,)).start()
                        elif old_status == "active" and new_status != "active":
                            try:
                                log_path = os.path.join(DATA_DIR, "air_raid_log.json")
                                l_data = json.load(open(log_path)) if os.path.exists(log_path) else []
                                l_data.append({"timestamp": now_dt.timestamp(), "event": "clear"})
                                json.dump(l_data, open(log_path, "w"), indent=2)
                            except: pass
                            start_ts = state.get("alert_start_time")
                            duration_str = ""
                            if start_ts:
                                duration_sec = int(now_dt.timestamp() - start_ts)
                                hours, mins = duration_sec // 3600, (duration_sec % 3600) // 60
                                duration_str = f"\nяка тривала {hours} год {mins} хв" if hours > 0 else f"\nяка тривала {mins} хв"
                            
                            if can_notify:
                                msg = f"✅ <b>{time_str} ВІДБІЙ ТРИВОГИ</b>{duration_str}"
                                threading.Thread(target=send_telegram, args=(msg,)).start()
                        state["alert_status"] = new_status
                        await save_state()
        except Exception as e: print(f"Error in alerts loop: {e}")
        await asyncio.sleep(60)

async def sync_schedules():
    """
    Syncs schedules from API or local parsing.
    Returns True if the schedule data has actually changed.
    """
    sync_success = False
    has_changed = False
    
    # Helper to get file hash
    def get_file_hash(filepath):
        if not os.path.exists(filepath): return None
        with open(filepath, "rb") as f: return hashlib.md5(f.read()).hexdigest()

    if SCHEDULE_API_URL:
        try:
            print(f"Syncing schedules from {SCHEDULE_API_URL}...")
            urls = {SCHEDULE_FILE: f"{SCHEDULE_API_URL}/last_schedules.json", HISTORY_FILE: f"{SCHEDULE_API_URL}/schedule_history.json"}
            
            old_hashes = {f: get_file_hash(f) for f in urls.keys()}
            
            for local_file, url in urls.items():
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    with open(local_file, "wb") as f: f.write(r.content)
            
            new_hashes = {f: get_file_hash(f) for f in urls.keys()}
            if old_hashes[SCHEDULE_FILE] != new_hashes[SCHEDULE_FILE]:
                has_changed = True
                print("API Sync: Schedule changed.")
            
            sync_success = True
        except Exception as e: print(f"Failed to sync schedules via API: {e}")
        
    if not sync_success:
        print("Starting local schedule parsing...")
        start_time = time.time()
        config_path = os.path.join(DATA_DIR, "config.json")
        result = await update_local_schedules(config_path, SCHEDULE_FILE)
        
        try:
            from app import PARSING_DURATION
            PARSING_DURATION.observe(time.time() - start_time)
        except ImportError: pass
            
        has_changed = result[1] if isinstance(result, tuple) and len(result) == 2 else False
        if has_changed:
            print("Local Parsing: Schedule changed.")

    if has_changed:
        # Trigger updates since data changed
        trigger_daily_report_update()
        trigger_weekly_report_update()
        
        # Check for specific outage slots to trigger immediate text alerts if needed
        try:
            if os.path.exists(SCHEDULE_FILE):
                with open(SCHEDULE_FILE, 'r') as f: data = json.load(f)
                should_alert = False
                for s_key in ['github', 'yasno']:
                    sources = data.get(s_key, {})
                    for group_name, days in sources.items():
                        for d, day_data in days.items():
                            if day_data.get('slots') and any(s is False for s in day_data['slots']):
                                should_alert = True; break
                        if should_alert: break
                    if should_alert: break
                
                if should_alert:
                    # Double check hash to avoid duplicate text alerts
                    slots_structure = {s_key: {gn: {d: day_data['slots'] for d, day_data in days.items() if day_data.get('slots') and any(s is False for s in day_data['slots'])} for gn, days in data.get(s_key, {}).items()} for s_key in ['github', 'yasno']}
                    current_hash = hashlib.md5(json.dumps(slots_structure, sort_keys=True).encode()).hexdigest()
                    
                    async with state_mgr:
                        if current_hash != state.get("last_schedule_hash"):
                            state["last_schedule_hash"] = current_hash
                            state["quiet_status"] = "active" # Disable quiet mode if schedule appears
                            await save_state()
                            print("Triggering text report alert due to schedule change...")
                            trigger_text_report_update()
        except Exception as e:
            print(f"Error in schedule change alert logic: {e}")
            
    return has_changed

def check_quiet_mode_eligibility():
    now = time.time()
    cutoff_24h_ago = now - (24 * 3600)
    try:
        if os.path.exists(EVENT_LOG_FILE):
            with open(EVENT_LOG_FILE, 'r') as f:
                logs = json.load(f)
                if any(entry.get("event") == "down" and entry.get("timestamp", 0) >= cutoff_24h_ago for entry in logs): return False
    except: return False
    try:
        if os.path.exists(SCHEDULE_FILE):
            with open(SCHEDULE_FILE, 'r') as f: data = json.load(f)
            now_dt = datetime.datetime.fromtimestamp(now, KYIV_TZ)
            today_str, tomorrow_str = now_dt.strftime("%Y-%m-%d"), (now_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            current_slot_idx = (now_dt.hour * 2) + (1 if now_dt.minute >= 30 else 0)
            for s_key in ['github', 'yasno']:
                for gn, days in data.get(s_key, {}).items():
                    all_slots = (days.get(today_str, {}).get('slots') or ([True]*48)) + (days.get(tomorrow_str, {}).get('slots') or ([True]*48))
                    if any(all_slots[i] is False for i in range(current_slot_idx, min(current_slot_idx + 48, len(all_slots)))): return False
        else: return False
    except: return False
    return True

async def schedule_loop():
    print("Schedule loop started...")
    weekly_sent_date = None
    last_prune_date = None
    
    while True:
        try:
            now = datetime.datetime.now(KYIV_TZ)
            now_str = now.strftime("%H:%M")
            today_date = now.strftime("%Y-%m-%d")
            
            # 1. Daily maintenance (at 00:01)
            if now.hour == 0 and now.minute == 1:
                trigger_daily_report_update(is_final=True)
                if last_prune_date != today_date:
                    prune_old_data()
                    create_backup("daily_auto")
                    last_prune_date = today_date
                await asyncio.sleep(65)
                continue

            # 2. Dynamic report times from config
            cfg = get_config()
            report_times = cfg.get("advanced", {}).get("notifications", {}).get("report_times", [])
            if now_str in report_times:
                print(f"Triggering scheduled report at {now_str}...")
                trigger_daily_report_update(is_final=False)
                await asyncio.sleep(65)
                continue

            # 3. Regular sync and status updates every 10 mins
            if now.minute % 10 == 0:
                # sync_schedules checks for plan changes
                await sync_schedules()

                # Always update reports to advance the "now" actual line
                trigger_daily_report_update()
                trigger_weekly_report_update()
                trigger_text_report_update()
                await update_quiet_status()                
            # 4. Weekly report (Monday morning)
            if now.weekday() == 0 and now.hour == 0 and 15 <= now.minute < 25:
                if weekly_sent_date != today_date:
                    try:
                        base_dir = os.path.dirname(os.path.abspath(__file__))
                        subprocess.run([sys.executable, "-m", "app.generate_weekly_report", "--date", (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")], check=True, cwd=os.path.dirname(base_dir))
                        weekly_sent_date = today_date
                    except Exception: pass
        except Exception as e:
            print(f"Critical error in schedule_loop: {e}")
            
        await asyncio.sleep(60)
