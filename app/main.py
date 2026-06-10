import requests
import httpx
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import os
import time
import re
from bs4 import BeautifulSoup
import threading
import asyncio
import cachetools
from fastapi import BackgroundTasks
import subprocess
import secrets
import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Header, Body, Query, HTTPException
from fastapi.responses import JSONResponse, FileResponse, PlainTextResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import make_asgi_app, Gauge, Histogram

from sse_starlette.sse import EventSourceResponse

# Запуск ініціалізації для нових користувачів
from scripts import bootstrap
bootstrap.perform_cold_start_if_needed()

from app.light_service import (
    load_state, save_state, state, state_mgr,
    monitor_loop, schedule_loop, get_current_time, format_duration,
    log_event, get_schedule_context, send_telegram,
    get_deviation_info, get_nearest_schedule_switch,
    format_event_message, get_next_scheduled_event,
    trigger_daily_report_update, trigger_weekly_report_update,
    get_air_raid_alert, get_push_interval, get_advanced_setting,
    update_quiet_status, sync_schedules,
    create_backup, list_backups, restore_backup,
    get_telegram_token, get_telegram_channel_id_cfg,
    ADMIN_CHAT_ID,
    KYIV_TZ, STATE_LOCK_FILE, DATA_DIR, EVENT_LOG_FILE
)

from app.push_service import save_subscription, remove_subscription, send_push_notification, VAPID_PUBLIC_KEY

# Structlog configuration
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("application_startup")
    await load_state()
    yield
    # Shutdown
    logger.info("application_shutdown")

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")
templates.env.cache = None  # Disable cache to bypass unhashable key bug

# Prometheus Metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

ACTIVE_SSE_CONNECTIONS = Gauge('flash_active_sse_connections', 'Number of active SSE connections')
PARSING_DURATION = Histogram('flash_parsing_duration_seconds', 'Time spent parsing schedules')

# --- SSE Logic ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[tuple[asyncio.Queue, str]] = []

    async def connect(self, q: asyncio.Queue, lang: str = "ua"):
        self.active_connections.append((q, lang))
        ACTIVE_SSE_CONNECTIONS.inc()

    def disconnect(self, q: asyncio.Queue):
        self.active_connections = [item for item in self.active_connections if item[0] != q]
        ACTIVE_SSE_CONNECTIONS.dec()

    async def broadcast(self, message_ua: dict, message_en: dict):
        for q, lang in self.active_connections:
            msg = message_en if lang == 'en' else message_ua
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

manager = ConnectionManager()

async def broadcast_state_update():
    status_data_ua = await api_status(lang="ua")
    status_data_en = await api_status(lang="en")
    await manager.broadcast(
        {"type": "update", "data": status_data_ua},
        {"type": "update", "data": status_data_en}
    )

# --- Caching ---
CACHE = cachetools.TTLCache(maxsize=100, ttl=60)
cache_lock = asyncio.Lock()

async def cached_fetch(key, func):
    async with cache_lock:
        if key in CACHE:
            return CACHE[key]
        
        try:
            if asyncio.iscoroutinefunction(func):
                data = await func()
            else:
                data = await asyncio.to_thread(func)
            CACHE[key] = data
            return data
        except Exception as e:
            logger.error("cache_update_error", key=key, error=str(e))
            # TTLCache doesn't keep expired, so we might return None if it fails
            return None

# --- PWA Routes ---

@app.get('/manifest.json')
def manifest():
    return FileResponse('static/manifest.json')

@app.get('/service-worker.js')
def service_worker():
    return FileResponse('static/service-worker.js')

@app.get('/static/{filename:path}')
def serve_static(filename: str):
    # Secure paths
    data_static_base = os.path.abspath(os.path.join(DATA_DIR, 'static'))
    code_static_base = os.path.abspath('static')
    
    data_static = os.path.abspath(os.path.join(data_static_base, filename))
    code_static = os.path.abspath(os.path.join(code_static_base, filename))
    
    file_path = None
    if data_static.startswith(data_static_base) and os.path.exists(data_static):
        file_path = data_static
    elif code_static.startswith(code_static_base) and os.path.exists(code_static):
        file_path = code_static
        
    if not file_path:
        raise HTTPException(status_code=404, detail="Not Found")
    
    headers = {}
    # Disable caching for images to ensure they refresh in PWA/Mobile
    if filename.endswith('.png'):
        headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        headers['Pragma'] = 'no-cache'
        headers['Expires'] = '0'
    
    return FileResponse(file_path, headers=headers)

@app.get('/health')
def health_check():
    return {"status": "ok"}

def get_radiation():
    # Return stable background value
    import random
    val = round(0.10 + random.uniform(0, 0.02), 2)
    return {
        "level": val,
        "unit": "мкЗв/год",
        "status": "normal"
    }

async def get_power_events_data(limit=5, lang='ua'):
    recent_events = []
    
    # Default schedule info
    sched_light_now, current_end, next_range, next_duration, is_emergency = get_schedule_context(lang=lang)
    if is_emergency:
        latest_event_text = "• possible emergency outages ⚠️" if lang == 'en' else "• можливі аварійні відключення ⚠️"
    elif (
        "не плануються" in next_range.lower() or 
        "невідомий час" in next_range.lower() or 
        "час невідомий" in next_range.lower() or 
        "час очікується" in next_range.lower() or
        "no outages" in next_range.lower() or
        "unknown" in next_range.lower()
    ):
        latest_event_text = "• No outages scheduled 🔆" if lang == 'en' else "• Відключення не плануються 🔆"
    else:
        prefix = "• Next scheduled: " if lang == 'en' else "• Наступне планове: "
        latest_event_text = f"{prefix}{next_range}"
    
    try:
        if os.path.exists(EVENT_LOG_FILE):
            with open(EVENT_LOG_FILE, "r") as f:
                logs = json.load(f)
                
                if len(logs) >= 1:
                    # Calculate durations
                    for i in range(len(logs)):
                        if i > 0:
                            logs[i]['duration_prev'] = logs[i]['timestamp'] - logs[i-1]['timestamp']
                        else:
                            logs[i]['duration_prev'] = None
                            
                    last_logs = logs[-limit:][::-1]
                    
                    for log in last_logs:
                        ts = log.get('timestamp', 0)
                        evt = log.get('event', 'unknown')
                        dur_sec = log.get('duration_prev')
                        
                        dt_str = datetime.fromtimestamp(ts).strftime("%d.%m %H:%M")
                        icon = "🟢" if evt == "up" else "🔴"
                        if lang == 'en':
                            text = "Power restored" if evt == "up" else "Power outage"
                            pre_text = "offline" if evt == "up" else "online"
                        else:
                            text = "Світло з'явилося" if evt == "up" else "Світло зникло"
                            pre_text = "не було" if evt == "up" else "було"
                        
                        dur_str = format_duration(dur_sec, lang=lang) if dur_sec else ""
                        
                        recent_events.append({
                            "time": dt_str,
                            "icon": icon,
                            "text": text,
                            "desc": f"({pre_text} {dur_str})" if dur_str else ""
                        })
                    
                    # Construct current status text
                    await load_state()
                    status = state.get("status", "unknown")

                    target_evt = "up" if status == "up" else "down"
                    
                    # Find the latest log entry that matches current status
                    last_match = None
                    for log in reversed(logs):
                        if log.get('event') == target_evt:
                            last_match = log
                            break
                    
                    if not last_match:
                        last_match = logs[-1]
                        
                    ts = last_match['timestamp']
                    evt = last_match['event']
                    
                    # --- NEW TEXT LOGIC ---
                    dev_msg = get_deviation_info(ts, evt == "up", lang=lang)
                    dev_line = ""
                    if dev_msg:
                        if lang == 'en':
                            m = re.search(r"(?:Powered ON|Powered OFF)\s+(later|earlier)\s+by\s+(.+)$", dev_msg)
                            if status == "up":
                                if m:
                                    timing = m.group(1)
                                    value = m.group(2)
                                    dev_line = f"• Restored {value} {timing}"
                                elif "strictly on schedule" in dev_msg:
                                    dev_line = "• Restored strictly on schedule"
                            else:
                                if m:
                                    timing = m.group(1)
                                    value = m.group(2)
                                    dev_line = f"• {value} {timing}"
                                elif "strictly on schedule" in dev_msg:
                                    dev_line = "• Strictly on schedule"
                        else:
                            m = re.search(r"(?:Увімкнули|Вимкнули)\s+(раніше|пізніше)\s+на\s+(.+)$", dev_msg)
                            if status == "up":
                                if m:
                                    timing = m.group(1)
                                    value = m.group(2)
                                    dev_line = f"• З'явилося на {value} {timing}"
                                elif "точно за графіком" in dev_msg:
                                    dev_line = "• З'явилося Точно за графіком"
                            else:
                                if m:
                                    timing = m.group(1)
                                    value = m.group(2)
                                    dev_line = f"• на {value} {timing}"
                                elif "точно за графіком" in dev_msg:
                                    dev_line = "• Точно за графіком"
                    
                    # Next event prediction
                    current_ts = time.time()
                    look_for_light = (status != "up") # If currently UP, look for OFF (False)
                    next_info = get_next_scheduled_event(current_ts, look_for_light)
                    wait_line = ""
                    if next_info:
                        if status == "up":
                            next_time = next_info["interval"].split('-')[0]
                            wait_line = f"• Outage at {next_time}" if lang == 'en' else f"• Вимкнення о {next_time}"
                        else:
                            wait_line = f"• Expected at {next_info['interval']}" if lang == 'en' else f"• Очікуємо о {next_info['interval']}"
                    
                    if is_emergency:
                        latest_event_text = "• possible emergency outages ⚠️" if lang == 'en' else "• можливі аварійні відключення ⚠️"
                    elif dev_line and wait_line:
                        latest_event_text = f"{dev_line}<br>{wait_line}"
                    elif dev_line:
                        latest_event_text = f"{dev_line}"
                    elif wait_line:
                        latest_event_text = f"{wait_line}"
                    elif (
                        "не плануються" in next_range.lower() or 
                        "невідомий час" in next_range.lower() or 
                        "час невідомий" in next_range.lower() or 
                        "час очікується" in next_range.lower() or
                        "no outages" in next_range.lower() or
                        "unknown" in next_range.lower()
                    ):
                        latest_event_text = "• No outages scheduled 🔆" if lang == 'en' else "• Відключення не плануються 🔆"
                    else:
                        prefix = "• Next scheduled: " if lang == 'en' else "• Наступне планове: "
                        latest_event_text = f"{prefix}{next_range}"
                    
    except Exception as e:
        logger.error("error_reading_events", error=str(e))
        pass
        
    return latest_event_text, recent_events

DAYS_UA = {0: "Понеділок", 1: "Вівторок", 2: "Середа", 3: "Четвер", 4: "П'ятниця", 5: "Субота", 6: "Неділя"}
DAYS_EN = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}

def render_day_schedule_html(slots, date_obj, lang='ua'):
    if not slots: return ""
    
    intervals_on = []
    intervals_off = []
    current_state = slots[0]
    start_idx = 0
    
    def format_slot_time(idx):
        mins = idx * 30
        h, m = mins // 60, mins % 60
        return f"{h:02d}:{m:02d}"
        
    for i in range(1, 48):
        if slots[i] != current_state:
            inv = {"state": current_state, "start": format_slot_time(start_idx), "end": format_slot_time(i), "duration": (i - start_idx) * 0.5}
            if current_state: intervals_on.append(inv)
            else: intervals_off.append(inv)
            start_idx = i
            current_state = slots[i]
    
    # Last interval
    inv = {"state": current_state, "start": format_slot_time(start_idx), "end": "24:00", "duration": (48 - start_idx) * 0.5}
    if current_state: intervals_on.append(inv)
    else: intervals_off.append(inv)

    total_on = sum(1 for s in slots if s) * 0.5
    total_off = 24.0 - total_on

    MONTHS_UA = {1: "Січня", 2: "Лютого", 3: "Березня", 4: "Квітня", 5: "Травня", 6: "Червня", 7: "Липня", 8: "Серпня", 9: "Вересня", 10: "Жовтня", 11: "Листопада", 12: "Грудня"}
    MONTHS_EN = {1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"}
    
    if lang == 'en':
        day_title = f"{date_obj.day} {MONTHS_EN[date_obj.month]} ({DAYS_EN[date_obj.weekday()]})"
    else:
        day_title = f"{date_obj.day} {MONTHS_UA[date_obj.month]} ({DAYS_UA[date_obj.weekday()]})"
    
    def fmt_dur(hours):
        val_str = f"{hours:g}"
        if lang == 'ua':
            return val_str.replace('.', ',')
        return val_str

    res = []
    res.append(f"<div class='schedule-date'>{day_title}</div>")
    res.append("<div class='schedule-columns'>")
    
    # Column ON
    on_header = "Power ON 🔆 " if lang == 'en' else "Увімкнення 🔆 "
    res.append("<div class='schedule-col'>")
    res.append(f"<div class='col-header on'>{on_header}{fmt_dur(total_on)}</div>")
    for inv in intervals_on:
        res.append(f"<div class='schedule-line on'><span class='schedule-time'>{inv['start']}</span><span class='time-sep'>-</span><span class='schedule-time'>{inv['end']}</span><span class='schedule-duration'>({fmt_dur(inv['duration'])})</span></div>")
    res.append("</div>")

    # Column OFF
    off_header = "Power OFF ✖️ " if lang == 'en' else "Вимкнення ✖️ "
    res.append("<div class='schedule-col'>")
    res.append(f"<div class='col-header off'>{off_header}{fmt_dur(total_off)}</div>")
    for inv in intervals_off:
        res.append(f"<div class='schedule-line off'><span class='schedule-time'>{inv['start']}</span><span class='time-sep'>-</span><span class='schedule-time'>{inv['end']}</span><span class='schedule-duration'>({fmt_dur(inv['duration'])})</span></div>")
    res.append("</div>")
    res.append("</div>")
    return "".join(res)

def get_today_schedule_text(lang='ua'):
    try:
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            config_path = "config.json"
        schedule_file = os.path.join(DATA_DIR, "last_schedules.json")
        if not os.path.exists(schedule_file):
            return "No schedule" if lang == 'en' else "Графік відсутній"

        with open(schedule_file, 'r') as f:
            data = json.load(f)

        now = datetime.now(KYIV_TZ)
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        # --- SMART SOURCE MERGE (Priority-Aware) ---
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f: cfg = json.load(f)
        user_priority = cfg.get("advanced", {}).get("data_sources", {}).get("priority", "yasno")
        priority_order = ['yasno', 'github']
        if user_priority in ['yasno', 'github']:
            priority_order = [user_priority] + [s for s in priority_order if s != user_priority]

        today_slots = None
        tomorrow_slots = None
        emergency_sources = []
        
        # 1. First Pass: Try to find any source with actual slots (following priority)
        found_source = None
        for s_name in priority_order:
            src = data.get(s_name)
            if not src: continue
            grp = list(src.keys())[0]
            day_data = src[grp].get(today_str)
            if day_data and day_data.get('slots'):
                today_slots = list(day_data['slots'])
                # Also get tomorrow if available from SAME source
                tm_data = src[grp].get(tomorrow_str)
                if tm_data and tm_data.get('slots'):
                    tomorrow_slots = list(tm_data['slots'])
                
                if day_data.get('status') == 'emergency':
                    name = "YASNO" if s_name == 'yasno' else ("DTEK" if lang == 'en' else "ДТЕК")
                    emergency_sources.append(name)
                
                found_source = s_name
                break
        
        # 2. Second Pass: If no slots found, check for emergency in any source
        if today_slots is None:
            for s_name in priority_order:
                src = data.get(s_name)
                if not src: continue
                grp = list(src.keys())[0]
                day_data = src[grp].get(today_str)
                if day_data and day_data.get('status') == 'emergency':
                    name = "YASNO" if s_name == 'yasno' else ("DTEK" if lang == 'en' else "ДТЕК")
                    if name not in emergency_sources: emergency_sources.append(name)

        if today_slots is None and not emergency_sources: 
            if lang == 'en':
                return "🟢 <b>No schedule</b><br><br>No outages scheduled (or data is not updated yet)."
            return "🟢 <b>Графік відсутній</b><br><br>Відключень не передбачається (або дані ще не оновлено)."

        output = []

        if emergency_sources:
            output.append("<div class='emergency-banner'>")
            title = "⚠️ Emergency outages!" if lang == 'en' else "⚠️ Екстрені відключення!"
            desc = "Schedules are currently inactive. Restoration time is unknown." if lang == 'en' else "Графіки наразі не діють. Час увімкнення невідомий."
            src_lbl = "Source: " if lang == 'en' else "Джерело: "
            output.append(f"<div class='emergency-title'>{title}</div>")
            output.append(f"<div class='emergency-desc'>{desc}</div>")
            output.append(f"<div class='source-label'>{src_lbl}{', '.join(emergency_sources)}</div>")
            output.append("</div>")

        # Render Today
        if today_slots:
            output.append(render_day_schedule_html(today_slots, now, lang=lang))

        # Render Tomorrow
        if tomorrow_slots:
            if any(s is not None for s in tomorrow_slots):
                output.append("<div class='schedule-divider'></div>")
                output.append(render_day_schedule_html(tomorrow_slots, now + timedelta(days=1), lang=lang))

        file_mtime = os.path.getmtime(schedule_file)
        dt_mtime = datetime.fromtimestamp(file_mtime, KYIV_TZ)

        # Only display the source that was actually used for the schedule
        active_sources = []
        if found_source:
            if found_source == 'yasno': active_sources.append("YASNO")
            elif found_source == 'github': active_sources.append("DTEK" if lang == 'en' else "ДТЕК")
            elif found_source == 'custom': active_sources.append("Custom URL" if lang == 'en' else "Свій URL")

        sources_str = f" [{', '.join(active_sources)}]" if active_sources else ""

        prefix_upd = "Updated: " if lang == 'en' else "Оновлено: "
        output.append(f"<div class='updated-time'>{prefix_upd}{dt_mtime.strftime('%H:%M')}{sources_str}</div>")

        return "".join(output)
    except Exception as e:
        logger.error("error_building_schedule_text", error=str(e))
        return "Error loading schedule" if lang == 'en' else "Помилка завантаження графіка"

async def get_air_quality(lang='ua'):
    try:
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            config_path = "config.json"
        if not os.path.exists(config_path):
            return {"status": "error", "text": "Config missing"}
            
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            
        aq_cfg = cfg.get("sources", {}).get("air_quality", {})
        if not aq_cfg:
            return {"status": "error", "text": "AQ source disabled"}

        # OpenMeteo for PM2.5/PM10
        lat = aq_cfg.get("lat", "50.45")
        lon = aq_cfg.get("lon", "30.52")
        om_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=pm10,pm2_5&hourly=pm2_5&past_days=1"
        
        # SaveEcoBot for Station-specific (Station 17095 or user-defined)
        seb_id = aq_cfg.get("seb_station", "17095")
        seb_url = f"https://www.saveecobot.com/station/{seb_id}.json"
        
        # Weather for Temp/Hum
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m&hourly=temperature_2m,relative_humidity_2m&past_days=1"

        def fetch_all():
            seb_data = {}
            try:
                r_seb = requests.get(seb_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
                if r_seb.status_code == 200:
                    seb_data = r_seb.json()
            except Exception as e:
                logger.error("seb_fetch_error", error=str(e))

            pm_data = {}
            try:
                pm_data = requests.get(om_url, timeout=5).json()
            except Exception as e:
                logger.error("om_fetch_error", error=str(e))

            w_data = {}
            try:
                w_data = requests.get(w_url, timeout=5).json()
            except Exception as e:
                logger.error("w_fetch_error", error=str(e))

            # Extract data
            pm25 = None
            pm10 = None
            pm1 = None
            seb_temp = None
            seb_hum = None
            
            if seb_data and "last_data" in seb_data:
                for item in seb_data["last_data"]:
                    phen = item.get("phenomenon")
                    val = item.get("value")
                    if phen == "pm25":
                        pm25 = val
                    elif phen == "pm10":
                        pm10 = val
                    elif phen == "pm1":
                        pm1 = val
                    elif phen == "temperature":
                        seb_temp = val
                    elif phen == "humidity":
                        seb_hum = val

            if pm25 is None:
                pm25 = pm_data.get('current', {}).get('pm2_5', 0) if pm_data else 0
            if pm10 is None:
                pm10 = pm_data.get('current', {}).get('pm10', 0) if pm_data else 0

            aqi = seb_data.get("aqi")
            if aqi is None:
                aqi = int(pm25 * 3)
            else:
                aqi = int(aqi)

            history_hourly = []
            history_times = []
            temp_history = []
            hum_history = []
            try:
                if pm_data:
                    pm25_hourly = pm_data.get('hourly', {}).get('pm2_5', [])
                    time_hourly = pm_data.get('hourly', {}).get('time', [])
                    if time_hourly:
                        now_iso = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:00")
                        try:
                            idx = time_hourly.index(now_iso)
                        except ValueError:
                            idx = len(time_hourly) - 1

                        if idx >= 23:
                            recent = pm25_hourly[idx-23:idx+1]
                            recent_times = time_hourly[idx-23:idx+1]
                        else:
                            recent = pm25_hourly[:idx+1]
                            recent_times = time_hourly[:idx+1]

                        for i in range(len(recent)):
                            val_h = recent[i] or 0
                            dt = datetime.fromisoformat(recent_times[i]).replace(tzinfo=ZoneInfo("UTC")).astimezone(KYIV_TZ)
                            history_hourly.append(int(val_h * 3))
                            history_times.append(dt.strftime("%H:%M"))

                if w_data:
                    temp_hourly = w_data.get('hourly', {}).get('temperature_2m', [])
                    hum_hourly = w_data.get('hourly', {}).get('relative_humidity_2m', [])
                    w_time_hourly = w_data.get('hourly', {}).get('time', [])
                    if w_time_hourly:
                        now_iso = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:00")
                        try:
                            idx = w_time_hourly.index(now_iso)
                        except ValueError:
                            idx = len(w_time_hourly) - 1

                        if idx >= 11:
                            recent_temp = temp_hourly[idx-11:idx+1]
                            recent_hum = hum_hourly[idx-11:idx+1]
                        else:
                            recent_temp = temp_hourly[:idx+1]
                            recent_hum = hum_hourly[:idx+1]

                        for i in range(len(recent_temp)):
                            t_val = recent_temp[i] if recent_temp[i] is not None else 0
                            h_val = recent_hum[i] if recent_hum[i] is not None else 0
                            try:
                                t_val = int(round(float(t_val)))
                            except (ValueError, TypeError):
                                pass
                            try:
                                h_val = int(round(float(h_val)))
                            except (ValueError, TypeError):
                                pass
                            temp_history.append(t_val)
                            hum_history.append(h_val)

            except Exception as e:
                logger.error("aq_history_error", error=str(e))

            status = "ok"
            status_text = "Good" if lang == 'en' else "Низький"
            if aqi > 50: 
                status = "warning"
                status_text = "Moderate" if lang == 'en' else "Помірне"
            if aqi > 100: 
                status = "danger"
                status_text = "Unhealthy" if lang == 'en' else "Високе"

            temp = seb_temp if seb_temp is not None else (w_data.get('current', {}).get('temperature_2m') if w_data else None)
            hum = seb_hum if seb_hum is not None else (w_data.get('current', {}).get('relative_humidity_2m') if w_data else None)
            if temp is not None:
                try:
                    temp = int(round(float(temp)))
                except (ValueError, TypeError):
                    pass
            if hum is not None:
                try:
                    hum = int(round(float(hum)))
                except (ValueError, TypeError):
                    pass

            loc_name = aq_cfg.get("location_name", "Київ")
            if lang == 'en' and loc_name == "Київ":
                loc_name = "Kyiv"

            return {
                "aqi": aqi,
                "history_hourly": history_hourly,
                "history_times": history_times,
                "temp_history": temp_history,
                "hum_history": hum_history,
                "status": status,
                "text": status_text,
                "pm25": pm25,
                "pm10": pm10,
                "pm1": pm1,
                "temp": temp,
                "hum": hum,
                "wind_speed": w_data.get('current', {}).get('wind_speed_10m') if w_data else None,
                "wind_dir": get_wind_label(w_data.get('current', {}).get('wind_direction_10m'), lang=lang) if w_data else "-",
                "location": loc_name
            }

        return await cached_fetch(f"air_quality_{lang}", fetch_all)
    except Exception as e:
        logger.error("aq_error", error=str(e))
        err_msg = "Data unavailable" if lang == 'en' else "Дані відсутні"
        return {"status": "error", "text": err_msg}

def get_wind_label(deg, lang='ua'):
    if deg is None: return "-"
    if lang == 'en':
        labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    else:
        labels = ["Пн", "ПнСх", "Сх", "ПдСх", "Пд", "ПдЗх", "Зх", "ПнЗх"]
    return labels[int((deg + 22.5) % 360 / 45)]

@app.get('/')
def index(request: Request):
    # Force dark theme preference for the dashboard
    return templates.TemplateResponse(request=request, name="index.html")

@app.get('/robots.txt')
def robots_txt():
    content = "User-agent: *\nDisallow: /admin\nDisallow: /api/\nAllow: /\n\nSitemap: https://power.srvrs.top/sitemap.xml"
    return PlainTextResponse(content)

@app.get('/sitemap.xml')
def sitemap_xml():
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://power.srvrs.top/</loc>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>'''
    return Response(content=content, media_type="application/xml")

@app.get('/admin')
def admin_panel(request: Request, t: str = Query(None), x_admin_token: str = Header(None, alias="X-Admin-Token")):
    token = t or x_admin_token
    if token and token == state.get('admin_token'):
        return templates.TemplateResponse(request=request, name="admin.html")
    return PlainTextResponse("Access Denied", status_code=403)

@app.get('/api/status')
async def api_status(lang: str = "ua"):
    await load_state()
    current_status = state.get("status", "unknown")
    # Ensure we return strictly "on" or "off" for UI icons
    ui_light_state = "on" if current_status == "up" else "off"
    
    latest_event_text, recent_events = await get_power_events_data(lang=lang)
    schedule_text = get_today_schedule_text(lang=lang)
    
    # Dashboard toggles
    show_aq = get_advanced_setting("dashboard", "show_aq", True)
    show_rad = get_advanced_setting("dashboard", "show_radiation", True)
    show_graphs = get_advanced_setting("dashboard", "show_temp_graph", True)
    show_charts = get_advanced_setting("dashboard", "show_charts", True)
    
    aq_data = await get_air_quality(lang=lang) if show_aq else None
    rad_data = get_radiation() if show_rad else None
    alert_data = get_air_raid_alert()
    
    # Extract group name
    config_path = os.path.join(DATA_DIR, "config.json")
    if not os.path.exists(config_path):
        config_path = "config.json"
    group_name = "---"
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            groups = cfg.get("settings", {}).get("groups", [])
            if groups:
                group_name = groups[0].replace('GPV', '')

    # Extra: get raw slots for graph bar
    now = datetime.now(KYIV_TZ)
    date_str = now.strftime("%Y-%m-%d")
    slots = [True] * 48
    sched_file = os.path.join(DATA_DIR, "last_schedules.json")
    if os.path.exists(sched_file):
        try:
            with open(sched_file, 'r') as f:
                s_data = json.load(f)
                merged = None
                for src in ['github', 'yasno']:
                    s = s_data.get(src)
                    if not s: continue
                    g_key = list(s.keys())[0]
                    day_data = s.get(g_key, {}).get(date_str, {}).get('slots')
                    if day_data:
                        if merged is None: merged = list(day_data)
                        else:
                            for i in range(min(len(merged), len(day_data))):
                                if day_data[i] is False: merged[i] = False
                if merged: slots = merged
        except: pass

    version = "v3.3.8"
    version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    if os.path.exists(version_path):
        with open(version_path, 'r') as f:
            version = f.read().strip()

    return {
        "light": ui_light_state,
        "light_event": latest_event_text,
        "recent_events": recent_events,
        "schedule_text": schedule_text,
        "schedule_slots": slots,
        "aqi": aq_data,
        "radiation": rad_data,
        "alert": alert_data,
        "group": group_name,
        "show_graphs": show_graphs,
        "show_charts": show_charts,
        "pending_confirmation": state.get("pending_confirmation", False),
        "timestamp": datetime.now(KYIV_TZ).strftime("%H:%M:%S"),
        "version": version
    }

# --- Web Push API ---
@app.get('/api/push/vapid-key')
def get_vapid_key():
    return {"publicKey": VAPID_PUBLIC_KEY}

@app.post('/api/push/subscribe')
async def push_subscribe(data: dict = Body(...)):
    subscription = data.get('subscription')
    if not subscription or not subscription.get('endpoint'):
        raise HTTPException(status_code=400, detail="Invalid subscription")
    save_subscription(subscription)
    return {"status": "ok"}

@app.post('/api/push/unsubscribe')
async def push_unsubscribe(data: dict = Body(...)):
    endpoint = data.get('endpoint', '')
    if not endpoint:
        raise HTTPException(status_code=400, detail="Missing endpoint")
    remove_subscription(endpoint)
    return {"status": "ok"}


@app.get('/api/push/{key}')
async def push_api(key: str, background_tasks: BackgroundTasks, x_secret_key: str = Header(None, alias="X-Secret-Key")):
    secret_key = x_secret_key or key
    actual_key = state.get('secret_key')
    if not secret_key or not actual_key or not secrets.compare_digest(secret_key, actual_key):
        return JSONResponse({"status": "error", "msg": "invalid_key"}, status_code=403)
        
    current_time = time.time()
    
    async with state_mgr:
        await load_state()  # Reload to get latest changes from other workers
        previous_status = state.get("status", "unknown")
        state["last_seen"] = current_time
        state["safety_net_pending"] = False # Reset on heartbeat
        state["safety_net_sent_at"] = 0     # Reset on heartbeat
        state["safety_net_triggered_for"] = 0 # Reset on heartbeat
        
        # If we are already UP, we do nothing to the status
        if previous_status == "up":
            pass
        elif previous_status == "down":
            logger.info("push_api_status_change", prev=previous_status, new="up")
            state["status"] = "up"
            state["came_up_at"] = current_time
            await log_event("up", current_time)
            
            # Quiet Mode check: skip message if status is 'quiet'
            if state.get("quiet_status") == "quiet":
                logger.info("Quiet mode active: Skipping 'Light Up' Telegram message.")
            else:
                msg = format_event_message(True, current_time, state.get("went_down_at", 0))
                background_tasks.add_task(send_telegram, msg)
                background_tasks.add_task(send_push_notification, "⚡ Світло з'явилось!", msg.split('\n')[0] if msg else "Електропостачання відновлено")
            background_tasks.add_task(broadcast_state_update)
        elif previous_status == "unknown":
            logger.info("push_api_status_change", prev=previous_status, new="up", msg="Cold start, no telegram alert")
            state["status"] = "up"
            state["came_up_at"] = current_time
            # Only log event internally, don't spam telegram on system restart
            await log_event("up", current_time)
            background_tasks.add_task(broadcast_state_update)
            
        await save_state()
    
    return {
    "status": "ok", 
    "msg": "heartbeat_received",
    "timestamp": datetime.now(KYIV_TZ).strftime("%H:%M:%S")
    }

@app.get('/api/confirm-outage/{action}/{key}')
async def confirm_outage_api(action: str, key: str, background_tasks: BackgroundTasks):
    actual_key = state.get('secret_key')
    if not key or not actual_key or not secrets.compare_digest(key, actual_key):
        return JSONResponse({"status": "error", "msg": "invalid_key"}, status_code=403)
        
    async with state_mgr:
        await load_state()
        if not state.get('pending_confirmation'):
            return {"status": "ok", "msg": "no_pending_confirmation"}
            
        if action == "confirm":
            state['quiet_status'] = 'active'
            state['pending_confirmation'] = False
            state['safety_net_pending'] = False
            down_time = state.get('went_down_at', time.time())
            msg = format_event_message(False, down_time, state.get("came_up_at", 0))
            background_tasks.add_task(send_telegram, msg)
            background_tasks.add_task(send_push_notification, "🔴 Відключення підтверджено", msg.split('\n')[0] if msg else "Електропостачання відсутнє")
            background_tasks.add_task(broadcast_state_update)
        elif action == "ignore":
            state['pending_confirmation'] = False
            background_tasks.add_task(broadcast_state_update)
            
        await save_state()
        
    return {"status": "ok", "action": action}

@app.get('/api/down/{key}')
async def down_api(key: str, background_tasks: BackgroundTasks, x_secret_key: str = Header(None, alias="X-Secret-Key")):
    secret_key = x_secret_key or key
    actual_key = state.get('secret_key')
    if not secret_key or not actual_key or not secrets.compare_digest(secret_key, actual_key):
        return JSONResponse({"status": "error", "msg": "invalid_key"}, status_code=403)
        
    current_time = time.time()
    
    async with state_mgr:
        await load_state()
        previous_status = state.get("status", "unknown")
        
        if previous_status == "up" or previous_status == "unknown":
            state["status"] = "down"
            state["went_down_at"] = current_time
            state["quiet_status"] = "active"
            await log_event("down", current_time)
            
            logger.info("Manual down API called: forcing quiet mode off and sending 'Light Down' message.")
            msg = format_event_message(False, current_time, state.get("came_up_at", 0))
            background_tasks.add_task(send_telegram, msg)
            background_tasks.add_task(send_push_notification, "🔴 Світло зникло!", msg.split('\n')[0] if msg else "Електропостачання відсутнє")
            background_tasks.add_task(broadcast_state_update)
            
        await save_state()
    
    return {
    "status": "ok", 
    "msg": "manual_down_received",
    "timestamp": datetime.now(KYIV_TZ).strftime("%H:%M:%S")
    }

@app.post('/api/tg/webhook')
async def tg_webhook(data: dict = Body(None), background_tasks: BackgroundTasks = BackgroundTasks()):
    if not data: return PlainTextResponse("OK")
    
    if 'callback_query' in data:
        cb = data['callback_query']
        cb_data = cb.get('data', '')
        msg_id = cb.get('message', {}).get('message_id')
        chat_id = cb.get('message', {}).get('chat', {}).get('id')
        
        if cb_data.startswith('confirm_down_'):
            async with state_mgr:
                await load_state()
                state['quiet_status'] = 'active'
                state['pending_confirmation'] = False
                state['safety_net_pending'] = False
    
                # Send the public Telegram alert
                try:
                    timestamp = float(cb_data.split('_')[-1])
                except:
                    timestamp = time.time()
    
                msg = format_event_message(False, timestamp, state.get("came_up_at", 0))
                background_tasks.add_task(send_telegram, msg)
                background_tasks.add_task(broadcast_state_update)
    
                # Update status
                state["status"] = "down"
                state["went_down_at"] = timestamp
                await log_event("down", timestamp)
                await save_state()

            # Answer callback
            client.answer_callback(cb["id"], "🔴 Підтверджено")

            # Edit message
            client.edit_message(msg_id, "🔴 Світло зникло (Підтверджено)")

        elif cb_data.startswith('ignore_down_'):
            async with state_mgr:
                await load_state()
                state['pending_confirmation'] = False
                await save_state()

            TelegramClient(get_telegram_token(), chat_id).answer_callback(cb['id'], "🟢 Ігноровано")

            TelegramClient(get_telegram_token(), chat_id).edit_message(msg_id, "🟢 Збій / Роботи (Ігноровано)")

        elif cb_data.startswith('sn_tech_'):
            # Show mute options
            timestamp = cb_data.split('_')[-1]
            TelegramClient(get_telegram_token(), chat_id).edit_message(msg_id, "🛠 На скільки часу вимкнути моніторинг?", reply_markup={
                    "inline_keyboard": [
                        [
                            {"text": "5 хв", "callback_data": f"mute_5_{timestamp}"},
                            {"text": "15 хв", "callback_data": f"mute_15_{timestamp}"},
                            {"text": "30 хв", "callback_data": f"mute_30_{timestamp}"}
                        ],
                        [
                            {"text": "1 год", "callback_data": f"mute_60_{timestamp}"},
                            {"text": "2 год", "callback_data": f"mute_120_{timestamp}"}
                        ],
                        [
                            {"text": "⬅️ Назад", "callback_data": f"sn_back_{timestamp}"}
                        ]
                    ]
                })

        elif cb_data.startswith('mute_'):
            parts = cb_data.split('_')
            minutes = int(parts[1])
            async with state_mgr:
                await load_state()
                state['muted_until'] = time.time() + (minutes * 60)
                state['safety_net_pending'] = False
                await save_state()

            requests.post(f"https://api.telegram.org/bot{get_telegram_token()}/answerCallbackQuery", json={
                "callback_query_id": cb['id'],
                "text": f"🛠 Моніторинг вимкнено на {minutes} хв"
            })

            requests.post(f"https://api.telegram.org/bot{get_telegram_token()}/editMessageText", json={
                "chat_id": chat_id,
                "message_id": msg_id,
                "text": f"🛠 Технічний збій. Моніторинг призупинено до {datetime.fromtimestamp(state['muted_until'], KYIV_TZ).strftime('%H:%M')}"
            })

        elif cb_data.startswith('sn_dontknow_'):
            async with state_mgr:
                await load_state()
                state['safety_net_pending'] = False
                await save_state()

            TelegramClient(get_telegram_token(), chat_id).answer_callback(cb['id'], "🤷‍♂️ Чекаємо 3 хв")

            TelegramClient(get_telegram_token(), chat_id).edit_message(msg_id, "🤷‍♂️ Невідомо. Чекаємо стандартний таймаут 3 хвилини.")

        elif cb_data.startswith('sn_down_'):
            # Confirm DOWN instantly
            async with state_mgr:
                await load_state()
                state['safety_net_pending'] = False
                state['quiet_status'] = 'active'
                state["status"] = "down"
                
                # Apply standard correction (last_seen + configured interval)
                last_seen = state.get("last_seen", time.time())
                down_time_ts = last_seen + get_push_interval()
                
                state["went_down_at"] = down_time_ts
                await log_event("down", down_time_ts)
                
                msg = format_event_message(False, down_time_ts, state.get("came_up_at", 0))
                background_tasks.add_task(send_telegram, msg)
                background_tasks.add_task(broadcast_state_update)
                await save_state()

            TelegramClient(get_telegram_token(), chat_id).answer_callback(cb['id'], "🔴 Підтверджено зникнення")

            TelegramClient(get_telegram_token(), chat_id).edit_message(msg_id, "🔴 Світло зникло (Підтверджено адміном)")

        elif cb_data.startswith('sn_back_'):
            timestamp = cb_data.split('_')[-1]
            # Restore safety net buttons
            msg = "🚨 <b>SAFETY NET: ВТРАТА ПУША!</b>\n\nВже 35 сек немає зв'язку. Що сталося?"
            TelegramClient(get_telegram_token(), chat_id).edit_message(msg_id, msg, reply_markup={
                    "inline_keyboard": [
                        [
                            {"text": "🔴 Світло зникло?", "callback_data": f"sn_down_{timestamp}"},
                            {"text": "🛠 Технічний збій?", "callback_data": f"sn_tech_{timestamp}"}
                        ],
                        [
                            {"text": "🤷‍♂️ Не знаю!", "callback_data": f"sn_dontknow_{timestamp}"}
                        ]
                    ]
                })
            
            TelegramClient(get_telegram_token(), chat_id).answer_callback(cb['id'], "Назад")
            
    return PlainTextResponse("OK")

# --- Admin APIs ---

def check_admin_token(request: Request):
    t = request.query_params.get('t') or request.headers.get('X-Admin-Token')
    admin_token = state.get('admin_token')
    if not t or not admin_token or not secrets.compare_digest(t, admin_token):
        return False
    return True

@app.get('/api/admin/data')
async def admin_data(request: Request):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
    
    config_path = os.path.join(DATA_DIR, "config.json")
    if not os.path.exists(config_path):
        config_path = "config.json"
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
    await load_state()
    
    logs = []
    if os.path.exists(EVENT_LOG_FILE):
        with open(EVENT_LOG_FILE, 'r') as f:
            logs = json.load(f)
            
    # Get version
    version = "v3.3.8"
    version_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "VERSION")
    if os.path.exists(version_path):
        with open(version_path, 'r') as f:
            version = f.read().strip()

    return {
        "config": config,
        "state": state,
        "logs": logs[-20:][::-1], # Last 20, newest first
        "version": version,
        "env": {
            "telegram_bot_token": get_telegram_token(),
            "telegram_channel_id": get_telegram_channel_id_cfg()
        }
    }

@app.post('/api/admin/config')
async def admin_config_post(request: Request, new_config: dict = Body(None)):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)

    if not new_config:
        return JSONResponse({"status": "error", "msg": "Invalid JSON"}, status_code=400)

    try:
        from app.models import AppConfig
        # Validate configuration before saving
        validated_config = AppConfig(**new_config).model_dump(exclude_unset=False, by_alias=True)

        # Create auto-backup before saving
        await asyncio.to_thread(create_backup, "auto_before_save")

        config_path = os.path.join(DATA_DIR, "config.json")
        
        def save_config():
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(validated_config, f, indent=2, ensure_ascii=False)
        
        await asyncio.to_thread(save_config)

        # Clear cache to reflect changes immediately (AQ, etc.)
        async with cache_lock:
            CACHE.clear()
            
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "msg": str(e)}, status_code=500)

@app.post('/api/admin/quiet/mode')
async def admin_quiet_mode(request: Request, data: dict = Body(None)):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
        
    if not data: data = {}
    mode = data.get('mode')
    unmute = data.get('unmute', False)

    if mode not in ['auto', 'forced_on', 'forced_off']:
        return JSONResponse({"status": "error", "msg": "Invalid mode"}, status_code=400)

    async with state_mgr:
        await load_state()
        state['quiet_mode'] = mode
        if unmute:
            state['muted_until'] = 0
            state['safety_net_pending'] = False
        await save_state()
    # Immediately recalculate actual status
    await update_quiet_status()
    return {"status": "ok"}

@app.post('/api/admin/safety_net/react')
async def admin_safety_net_react(request: Request, data: dict = Body(None), background_tasks: BackgroundTasks = BackgroundTasks()):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)

    if not data: data = {}
    action = data.get('action')
    value = data.get('value') # For tech mute duration

    async with state_mgr:
        await load_state()
        if action == 'down':
            state['safety_net_pending'] = False
            state["status"] = "down"
            # Apply standard correction (last_seen + configured interval)
            last_seen = state.get("last_seen", time.time())
            down_time_ts = last_seen + get_push_interval()
            state["went_down_at"] = down_time_ts
            await log_event("down", down_time_ts)
            msg = format_event_message(False, down_time_ts, state.get("came_up_at", 0))
            background_tasks.add_task(send_telegram, msg)
            background_tasks.add_task(broadcast_state_update)
        
        elif action == 'tech':
            minutes = int(value or 30)
            state['muted_until'] = time.time() + (minutes * 60)
            state['safety_net_pending'] = False
            
        elif action == 'dontknow':
            state['safety_net_pending'] = False
            
        elif action == 'confirm':
            state['quiet_status'] = 'active'
            state['pending_confirmation'] = False
            state['safety_net_pending'] = False
            down_time = state.get('went_down_at', time.time())
            msg = format_event_message(False, down_time, state.get("came_up_at", 0))
            background_tasks.add_task(send_telegram, msg)
            background_tasks.add_task(broadcast_state_update)
            
        elif action == 'ignore':
            state['pending_confirmation'] = False
            background_tasks.add_task(broadcast_state_update)
            
        await save_state()

    return {"status": "ok"}

@app.post('/api/admin/logs/add')
async def admin_logs_add(request: Request, data: dict = Body(None)):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)

    if not data: data = {}
    event = data.get('event')
    timestamp = data.get('timestamp')

    if not event or not timestamp:
        return JSONResponse({"status": "error", "msg": "Missing event or timestamp"}, status_code=400)

    try:
        await log_event(event, float(timestamp))
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "msg": str(e)}, status_code=500)

@app.delete('/api/admin/logs/{timestamp}')
async def admin_logs_delete(request: Request, timestamp: float):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)

    try:
        if os.path.exists(EVENT_LOG_FILE):
            with open(EVENT_LOG_FILE, 'r') as f:
                logs = json.load(f)

            # Filter out the log with given timestamp (within small margin for float)
            new_logs = [log for log in logs if abs(log.get('timestamp', 0) - timestamp) > 0.1]

            with open(EVENT_LOG_FILE, 'w') as f:
                json.dump(new_logs, f, indent=2)

        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"status": "error", "msg": str(e)}, status_code=500)
@app.post('/api/admin/service/restart')
async def admin_service_restart(request: Request, background_tasks: BackgroundTasks = BackgroundTasks()):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)

    try:
        def restart():
            time.sleep(1)
            subprocess.run(["systemctl", "restart", "power-safety-ua.service", "power-safety-ua-worker.service"])

        threading.Thread(target=restart).start()
        return {"status": "ok", "msg": "Services restarting..."}
    except Exception as e:
        return JSONResponse({"status": "error", "msg": str(e)}, status_code=500)

@app.post('/api/admin/schedules/sync')
async def admin_schedules_sync(request: Request, background_tasks: BackgroundTasks = BackgroundTasks()):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)

    try:
        background_tasks.add_task(sync_schedules)
        return {"status": "ok", "msg": "Sync triggered"}
    except Exception as e:
        return JSONResponse({"status": "error", "msg": str(e)}, status_code=500)

@app.get('/api/admin/backups')
async def admin_backups_list(request: Request):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
    return await asyncio.to_thread(list_backups)

@app.post('/api/admin/backups/create')
async def admin_backups_create(request: Request):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
    name = await asyncio.to_thread(create_backup, "manual")
    return {"status": "ok", "name": name}

@app.post('/api/admin/backups/restore')
async def admin_backups_restore(request: Request, data: dict = Body(None)):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
    if not data: data = {}
    filename = data.get("filename")
    if not filename:
        return JSONResponse({"status": "error", "msg": "Filename required"}, status_code=400)
    
    success, msg = await asyncio.to_thread(restore_backup, filename)
    if success:
        return {"status": "ok", "msg": "Restored successfully. Restarting services..."}
    else:
        return JSONResponse({"status": "error", "msg": msg}, status_code=500)

@app.post('/api/admin/security/regen_push_key')
async def admin_regen_push_key(request: Request):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
    
    async with state_mgr:
        await load_state()
        new_key = secrets.token_urlsafe(16)
        state["secret_key"] = new_key
        await save_state()
    
    return {"status": "ok", "new_key": new_key}

@app.post('/api/admin/security/regen_admin_token')
async def admin_regen_token(request: Request):
    if not check_admin_token(request):
        return JSONResponse({"status": "error", "msg": "Access Denied"}, status_code=403)
    
    async with state_mgr:
        await load_state()
        new_token = secrets.token_urlsafe(16)
        state["admin_token"] = new_token
        await save_state()
    
    return {"status": "ok", "new_token": new_token}




@app.get('/api/status/stream')
async def status_stream(request: Request, lang: str = "ua"):
    
    async def event_generator():
        q = asyncio.Queue(maxsize=100)
        await manager.connect(q, lang)
        try:
            # Initial burst
            initial_data = await api_status(lang=lang)
            yield {
                "event": "update",
                "data": json.dumps({"type": "update", "data": initial_data})
            }
            
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield {
                        "event": "update",
                        "data": json.dumps(message)
                    }
                except asyncio.TimeoutError:
                    yield {
                        "event": "ping",
                        "data": "keep-alive"
                    }
        finally:
            manager.disconnect(q)
            
    return EventSourceResponse(event_generator())

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=5050)
