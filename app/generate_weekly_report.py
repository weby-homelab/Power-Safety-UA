import json
import os
import datetime
import shutil
from zoneinfo import ZoneInfo
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import necessary functions from the daily report script to reuse logic
from app.generate_daily_report import load_events, get_intervals_for_date, format_duration, KYIV_TZ, load_schedule_slots, get_quiet_status, get_now

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
HISTORY_FILE = os.path.join(DATA_DIR, "schedule_history.json")


def get_alert_intervals(target_date):
    import os, json, datetime
    from zoneinfo import ZoneInfo
    log_file = "data/air_raid_log.json"
    if not os.path.exists(log_file):
        return []
    try:
        with open(log_file, "r") as f:
            data = json.load(f)
    except Exception:
        return []
    
    intervals = []
    current_start = None
    KYIV_TZ = ZoneInfo("Europe/Kyiv")
    day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=KYIV_TZ)
    day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=KYIV_TZ)
    
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
                
    if current_start is not None:
        start = max(current_start, day_start)
        now = get_now()
        end = min(now, day_end)
        if start < end:
            intervals.append((start, end, True))
            
    return intervals


def get_weekly_alerts_stats(monday, sunday):
    import os, json, datetime
    from zoneinfo import ZoneInfo
    KYIV_TZ = ZoneInfo("Europe/Kyiv")
    
    # Start and end of the week
    week_start = datetime.datetime.combine(monday, datetime.time.min).replace(tzinfo=KYIV_TZ)
    week_end = datetime.datetime.combine(sunday, datetime.time.max).replace(tzinfo=KYIV_TZ)
    
    log_file = os.path.join(DATA_DIR, "air_raid_log.json")
    if not os.path.exists(log_file):
        return 0, 0, 0.0
        
    try:
        with open(log_file, "r") as f:
            data = json.load(f)
    except Exception:
        return 0, 0, 0.0
        
    alerts = []
    current_start = None
    
    for event in data:
        dt = datetime.datetime.fromtimestamp(event["timestamp"], tz=KYIV_TZ)
        if event["event"] == "active":
            if current_start is None:
                current_start = dt
        elif event["event"] == "clear":
            if current_start is not None:
                # Truncate to the week range
                start = max(current_start, week_start)
                end = min(dt, week_end)
                if start < end:
                    alerts.append((start, end))
                current_start = None
                
    if current_start is not None:
        start = max(current_start, week_start)
        now = get_now()
        end = min(now, week_end)
        if start < end:
            alerts.append((start, end))
            
    count = len(alerts)
    total_duration_sec = sum((end - start).total_seconds() for start, end in alerts)
    total_hours = total_duration_sec / 3600.0
    
    # Percentage of weekly time
    total_week_hours = 168.0
    pct = (total_hours / total_week_hours * 100) if total_week_hours > 0 else 0
    
    return count, total_duration_sec, pct



def get_schedule_slots(date_obj):
    """
    Wrapper around load_schedule_slots from daily report to ensure consistent logic.
    """
    try:
        slots = load_schedule_slots(date_obj)
        return slots
    except:
        return [True] * 48

def slots_to_intervals(slots):
    if not slots: return []
    intervals = []
    start_idx = 0
    current_state = slots[0]
    for i in range(1, len(slots)):
        if slots[i] != current_state:
            duration = (i - start_idx) * 0.5
            intervals.append((start_idx * 0.5, duration, current_state))
            current_state = slots[i]
            start_idx = i
    duration = (len(slots) - start_idx) * 0.5
    intervals.append((start_idx * 0.5, duration, current_state))
    return intervals

def get_weekly_stats(start_date, end_date, events):
    """
    Calculates stats for a specific range [start_date, end_date].
    Includes Plan vs Fact analysis.
    """
    total_up_sec = 0
    total_down_sec = 0
    total_plan_up = 0
    total_plan_down = 0
    
    days_stats = []
    
    current = start_date
    while current <= end_date:
        # --- Actual Data ---
        intervals = get_intervals_for_date(current, events)
        day_up = 0
        day_down = 0
        
        for start, end, state in intervals:
            duration = (end - start).total_seconds()
            if state == 'up' or state == 'unknown':
                day_up += duration
            elif state == 'down':
                day_down += duration
        
        # --- Planned Data ---
        slots = get_schedule_slots(current)
        if slots:
            plan_up = sum(1 for s in slots if s) * 0.5
            plan_down = sum(1 for s in slots if not s) * 0.5
        else:
            plan_up, plan_down = 0, 0

        day_up_h = day_up / 3600
        diff = day_up_h - plan_up if slots else 0
        
        total_up_sec += day_up
        total_down_sec += day_down
        if slots:
            total_plan_up += plan_up
            total_plan_down += plan_down
            
        days_stats.append({
            'date': current,
            'up': day_up,
            'down': day_down,
            'plan_up': plan_up,
            'plan_down': plan_down,
            'diff': diff,
            'has_plan': bool(slots),
            'intervals': intervals
        })
        current += datetime.timedelta(days=1)
        
    sorted_by_outage = sorted(days_stats, key=lambda x: x['down'])
    days_with_plan = [d for d in days_stats if d['has_plan']]
    
    if days_with_plan:
        easiest_day = max(days_with_plan, key=lambda x: x['diff'])
        hardest_day = min(days_with_plan, key=lambda x: x['diff'])
    else:
        easiest_day = None
        hardest_day = None

    return {
        'total_up': total_up_sec,
        'total_down': total_down_sec,
        'total_plan_up': total_plan_up,
        'total_plan_down': total_plan_down,
        'best_day': sorted_by_outage[0],
        'worst_day': sorted_by_outage[-1],
        'easiest_day': easiest_day,
        'hardest_day': hardest_day,
        'daily_data': days_stats
    }

def generate_weekly_chart(end_date, daily_data, theme='dark', lang='ua'):
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
        fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        
        # Colors
        color_map = {'up': fact_on_color, 'down': fact_off_color, 'unknown': fact_on_color}
        sched_map = {True: plan_on_color, False: plan_off_color} 
        
        y_labels = []
        y_ticks = []
        
        dummy_date = datetime.date(2000, 1, 1)
        
        # Get coordinates from config
        config_path = os.path.join(DATA_DIR, "config.json")
        if not os.path.exists(config_path):
            config_path = "config.json"
        
        cfg = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            except Exception:
                pass
                
        aq_cfg = cfg.get("sources", {}).get("air_quality", {})
        lat = aq_cfg.get("lat", "50.408")
        lon = aq_cfg.get("lon", "30.400")

        # Fetch weekly AQI in one request
        aqi_by_date = {}
        try:
            start_date = daily_data[0]['date']
            end_date = daily_data[-1]['date']
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&start_date={start_str}&end_date={end_str}&hourly=us_aqi&timezone=Europe%2FKyiv"
            r_aq = requests.get(aq_url, timeout=15)
            if r_aq.status_code == 200:
                aq_data = r_aq.json()
                us_aqi_hourly = aq_data.get("hourly", {}).get("us_aqi", [])
                time_hourly = aq_data.get("hourly", {}).get("time", [])
                for t_str, val in zip(time_hourly, us_aqi_hourly):
                    dt = datetime.datetime.fromisoformat(t_str)
                    d_str = dt.strftime("%Y-%m-%d")
                    if d_str not in aqi_by_date:
                        aqi_by_date[d_str] = []
                    aqi_by_date[d_str].append((dt.hour, val))
        except Exception as e:
            print(f"Error fetching weekly AQI data: {e}")
        
        for i, day_info in enumerate(daily_data):
            day_date = day_info['date']
            intervals = day_info['intervals']
            
            y_pos = 11 - i * 1.8
            
            if lang == 'en':
                day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            else:
                day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            label = f"{day_names[day_date.weekday()]} {day_date.strftime('%d.%m')}"
            y_labels.append(label)
            y_ticks.append(y_pos + 0.18) # Center of the day stack
            
            # --- 1. Draw Actual Data (Top Strip) ---
            now_kyiv = get_now()
            
            if day_date <= now_kyiv.date():
                for start, end, state in intervals:
                    if day_date == now_kyiv.date():
                        if start > now_kyiv: continue 
                        if end > now_kyiv: end = now_kyiv
                    
                    d_start = datetime.datetime.combine(dummy_date, start.time())
                    d_end = datetime.datetime.combine(dummy_date, end.time())
                    
                    if end.time() == datetime.time.min and end != start:
                         d_end += datetime.timedelta(days=1)
                    elif d_end < d_start:
                         d_end += datetime.timedelta(days=1)
                        
                    start_num = mdates.date2num(d_start)
                    end_num = mdates.date2num(d_end)
                    duration_num = end_num - start_num
                    
                    if duration_num > 0:
                        color = color_map.get(state, fact_on_color)
                        ax.broken_barh([(start_num, duration_num)], (y_pos + 0.54, 0.36), facecolors=color, edgecolor='none')

            # --- 2. Draw Schedule Data (Second Strip) ---
            slots = get_schedule_slots(day_date)
            if slots:
                sched_intervals = slots_to_intervals(slots)
                for start_h, duration_h, is_on in sched_intervals:
                    s_date = datetime.datetime.combine(dummy_date, datetime.time.min) + datetime.timedelta(hours=start_h)
                    start_n = mdates.date2num(s_date)
                    duration_n = duration_h / 24.0
                    
                    color = sched_map.get(is_on, plan_off_color)
                    ax.broken_barh([(start_n, duration_n)], (y_pos + 0.18, 0.36), facecolors=color, edgecolor='none')


            # --- 3. Draw Alert Data (Third Strip) ---
            alert_on_color = '#FFFDE7' # Pastel white-yellow for alerts
            alert_off_color = '#334155' if theme == 'dark' else '#cbd5e1'
            
            if day_date == now_kyiv.date():
                x_end_dt = datetime.datetime.combine(dummy_date, now_kyiv.time())
            elif day_date < now_kyiv.date():
                x_end_dt = datetime.datetime.combine(dummy_date, datetime.time.max)
            else:
                x_end_dt = datetime.datetime.combine(dummy_date, datetime.time.min) # Future day: don't draw
            
            x_start_dt = datetime.datetime.combine(dummy_date, datetime.time.min)
            x_start_num = mdates.date2num(x_start_dt)
            x_end_num = mdates.date2num(x_end_dt)
            duration_x = x_end_num - x_start_num
            
            if duration_x > 0:
                ax.broken_barh([(x_start_num, duration_x)], (y_pos - 0.18, 0.36), facecolors=alert_off_color, edgecolor='none')
                
                alert_intervals = get_alert_intervals(day_date)
                for start, end, is_alert in alert_intervals:
                    if is_alert:
                        if day_date == now_kyiv.date():
                            if start > now_kyiv:
                                continue
                            if end > now_kyiv:
                                end = now_kyiv
                        
                        d_start = datetime.datetime.combine(dummy_date, start.time())
                        d_end = datetime.datetime.combine(dummy_date, end.time())
                        
                        if end.time() == datetime.time.min and end != start:
                             d_end += datetime.timedelta(days=1)
                        elif d_end < d_start:
                             d_end += datetime.timedelta(days=1)
                            
                        start_num = mdates.date2num(d_start)
                        duration_num = mdates.date2num(d_end) - start_num
                        
                        if duration_num > 0:
                            ax.broken_barh([(start_num, duration_num)], (y_pos - 0.18, 0.36), facecolors=alert_on_color, edgecolor='none')


            # --- 4. Draw AQI Data (Fourth Strip) ---
            d_str = day_date.strftime("%Y-%m-%d")
            aqi_intervals = []
            
            history_file = os.path.join(DATA_DIR, "metrics_history.json")
            history_data = []
            if os.path.exists(history_file):
                try:
                    with open(history_file, 'r') as f:
                        history_data = json.load(f)
                except: pass

            target_day_metrics = []
            for item in history_data:
                dt_metric = datetime.datetime.fromtimestamp(item.get("timestamp", 0), KYIV_TZ)
                if dt_metric.date() == day_date:
                    target_day_metrics.append(item)

            target_day_metrics.sort(key=lambda x: x.get("timestamp", 0))

            if target_day_metrics:
                for idx, item in enumerate(target_day_metrics):
                    ts = item.get("timestamp", 0)
                    aqi_val = item.get("aqi", 0)
                    
                    if aqi_val <= 50:
                        color = "#22c55e" # Green
                    elif aqi_val <= 100:
                        color = "#eab308" # Yellow
                    else:
                        color = "#ef4444" # Red
                    
                    start_t = datetime.datetime.fromtimestamp(ts, KYIV_TZ)
                    if start_t > now_kyiv:
                        continue
                    
                    if idx < len(target_day_metrics) - 1:
                        next_ts = target_day_metrics[idx + 1].get("timestamp", 0)
                        end_t = datetime.datetime.fromtimestamp(min(next_ts, ts + 600), KYIV_TZ)
                    else:
                        end_t = start_t + datetime.timedelta(minutes=10)
                    
                    if end_t > now_kyiv:
                        end_t = now_kyiv
                    
                    if end_t > start_t:
                        aqi_intervals.append((start_t, end_t, color))
            else:
                # Fallback to Open-Meteo API hourly data if local history is empty
                hourly_pm = aqi_by_date.get(d_str, [])
                if not hourly_pm:
                    if day_date <= now_kyiv.date():
                        limit_h = now_kyiv.hour + 1 if day_date == now_kyiv.date() else 24
                        hourly_pm = [(h, None) for h in range(limit_h)]
                    else:
                        hourly_pm = []
                
                for hour, val in hourly_pm:
                    s_date = datetime.datetime.combine(day_date, datetime.time(hour, 0)).replace(tzinfo=KYIV_TZ)
                    if s_date > now_kyiv:
                        continue
                        
                    if val is None:
                        color = "#64748b" # Gray fallback
                    else:
                        aqi_val = int(val)
                        if aqi_val <= 50: color = "#22c55e"
                        elif aqi_val <= 100: color = "#eab308"
                        else: color = "#ef4444"
                        
                    end_t = s_date + datetime.timedelta(hours=1)
                    if end_t > now_kyiv:
                        end_t = now_kyiv
                    aqi_intervals.append((s_date, end_t, color))

            # Render AQI intervals translated to dummy_date
            for start, end, color in aqi_intervals:
                d_start = datetime.datetime.combine(dummy_date, start.time())
                d_end = datetime.datetime.combine(dummy_date, end.time())
                
                if end.time() == datetime.time.min and end != start:
                    d_end += datetime.timedelta(days=1)
                elif d_end < d_start:
                    d_end += datetime.timedelta(days=1)
                    
                start_num = mdates.date2num(d_start)
                duration_num = mdates.date2num(d_end) - start_num
                if duration_num > 0:
                    ax.broken_barh([(start_num, duration_num)], (y_pos - 0.54, 0.36), facecolors=color, edgecolor='none')


            # --- Separator Lines ---
            ax.axhline(y=y_pos + 0.54, color=bg_color, linewidth=0.5, zorder=5)
            ax.axhline(y=y_pos + 0.18, color=bg_color, linewidth=0.5, zorder=5)
            ax.axhline(y=y_pos - 0.18, color=bg_color, linewidth=0.5, zorder=5)

            # --- Hour Markers on the Bars (Background Color) ---
            hour_points = [mdates.date2num(datetime.datetime.combine(dummy_date, datetime.time(h, 0))) for h in range(1, 24)]
            ax.vlines(hour_points, y_pos - 0.54, y_pos + 0.90, colors=bg_color, linewidth=0.8, zorder=6)

        # Formatting
        ax.set_ylim(-1.0, 12.5)
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_labels, color=text_color)
        ax.tick_params(axis='x', colors=text_color)
        ax.tick_params(axis='y', colors=text_color)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color(text_color)
        
        x_start = datetime.datetime(2000, 1, 1, 0, 0)
        x_end = datetime.datetime(2000, 1, 1, 23, 59)
        ax.set_xlim(mdates.date2num(x_start), mdates.date2num(x_end))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
        
        if lang == 'en':
            title_text = f"Electricity Week ({daily_data[0]['date'].strftime('%d.%m')} - {daily_data[-1]['date'].strftime('%d.%m')})"
        else:
            title_text = f"Енергетичний тиждень ({daily_data[0]['date'].strftime('%d.%m')} - {daily_data[-1]['date'].strftime('%d.%m')})"
        ax.set_title(title_text, fontsize=14, color=text_color)
        
        import matplotlib.patches as mpatches
        if lang == 'en':
            label_fact_on = 'Power ON'
            label_fact_off = 'Power OFF'
            label_plan_on = 'Schedule: ON'
            label_plan_off = 'Schedule: OFF'
            label_alert = 'Air Raid Alert'
            label_alert_off = 'No Alerts'
            label_aqi_good = 'AQI: Good'
            label_aqi_mod = 'AQI: Moderate'
            label_aqi_unhealthy = 'AQI: Unhealthy'
        else:
            label_fact_on = 'Світло є'
            label_fact_off = 'Світла немає'
            label_plan_on = 'Графік: Є'
            label_plan_off = 'Графік: Немає'
            label_alert = 'Тривога'
            label_alert_off = 'Немає тривог'
            label_aqi_good = 'AQI: Добре'
            label_aqi_mod = 'AQI: Помірне'
            label_aqi_unhealthy = 'AQI: Шкідливе'

        green_patch = mpatches.Patch(color=fact_on_color, label=label_fact_on)
        red_patch = mpatches.Patch(color=fact_off_color, label=label_fact_off)
        yellow_patch = mpatches.Patch(color=plan_on_color, label=label_plan_on)
        gray_patch = mpatches.Patch(color=plan_off_color, label=label_plan_off)
        alert_patch = mpatches.Patch(color='#FFFDE7', label=label_alert)
        alert_off_patch = mpatches.Patch(color=('#334155' if theme == 'dark' else '#cbd5e1'), label=label_alert_off)
        
        aqi_green = mpatches.Patch(color='#22c55e', label=label_aqi_good)
        aqi_yellow = mpatches.Patch(color='#eab308', label=label_aqi_mod)
        aqi_red = mpatches.Patch(color='#ef4444', label=label_aqi_unhealthy)

        legend = plt.legend(handles=[green_patch, red_patch, yellow_patch, gray_patch, alert_patch, alert_off_patch, aqi_green, aqi_yellow, aqi_red],
                   loc='upper center', bbox_to_anchor=(0.5, -0.1),
                   fancybox=False, frameon=False, shadow=False, ncol=3, fontsize='small')
        plt.setp(legend.get_texts(), color=text_color)
        
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.22)
        
        suffix = ""
        if theme == 'light':
            suffix += "_light"
        if lang == 'en':
            suffix += "_en"
        filename = os.path.join(DATA_DIR, f"weekly_report_{end_date.strftime('%Y-%m-%d')}{suffix}.png")
        plt.savefig(filename, dpi=100, facecolor=fig.get_facecolor())
        plt.close()
    
    return filename

def send_telegram_photo(photo_path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(photo_path, 'rb') as f:
        files = {'photo': f}
        data = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML', 'disable_notification': True}
        try:
            r = requests.post(url, files=files, data=data, timeout=20)
            if r.status_code == 200:
                print("Weekly report sent successfully.")
            else:
                print(f"Failed to send weekly report: {r.text}")
        except Exception as e:
            print(f"Error sending weekly report: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date YYYY-MM-DD")
    parser.add_argument("--output", help="Save chart to file instead of sending")
    parser.add_argument("--no-send", action="store_true", help="Do not send to Telegram")
    args = parser.parse_args()

    now = get_now()
    if args.date:
        target_date = datetime.datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = now.date()

    monday = target_date - datetime.timedelta(days=target_date.weekday())
    sunday = monday + datetime.timedelta(days=6)
        
    print(f"Generating weekly report for: {monday} to {sunday}...")
    
    events = load_events()
    stats = get_weekly_stats(monday, sunday, events)
    
    # If output is specified, use that filename
    if args.output:
        temp_filename = generate_weekly_chart(sunday, stats['daily_data'], theme='dark', lang='ua')
        temp_light = generate_weekly_chart(sunday, stats['daily_data'], theme='light', lang='ua')
        temp_filename_en = generate_weekly_chart(sunday, stats['daily_data'], theme='dark', lang='en')
        temp_light_en = generate_weekly_chart(sunday, stats['daily_data'], theme='light', lang='en')
        
        if os.path.exists(temp_filename):
            if os.path.exists(args.output):
                os.remove(args.output)
            shutil.move(temp_filename, args.output)
            print(f"Chart saved to {args.output}")
            
        base, ext = os.path.splitext(args.output)
        light_output = f"{base}_light{ext}"
        
        if os.path.exists(temp_light):
            if os.path.exists(light_output):
                os.remove(light_output)
            shutil.move(temp_light, light_output)
            print(f"Light chart saved to {light_output}")
            
        en_output = f"{base}_en{ext}"
        if os.path.exists(temp_filename_en):
            if os.path.exists(en_output):
                os.remove(en_output)
            shutil.move(temp_filename_en, en_output)
            print(f"EN chart saved to {en_output}")
            
        light_en_output = f"{base}_light_en{ext}"
        if os.path.exists(temp_light_en):
            if os.path.exists(light_en_output):
                os.remove(light_en_output)
            shutil.move(temp_light_en, light_en_output)
            print(f"EN Light chart saved to {light_en_output}")
            
        sys.exit(0)

    # Standard Telegram Flow
    filename = generate_weekly_chart(sunday, stats['daily_data'], theme='dark', lang='ua')
    filename_light = generate_weekly_chart(sunday, stats['daily_data'], theme='light', lang='ua')
    filename_en = generate_weekly_chart(sunday, stats['daily_data'], theme='dark', lang='en')
    filename_light_en = generate_weekly_chart(sunday, stats['daily_data'], theme='light', lang='en')
    
    # Save copy for Web Dashboard
    web_dir = os.path.join(DATA_DIR, "static")
    if not os.path.exists(web_dir): os.makedirs(web_dir)
    shutil.copy(filename, os.path.join(web_dir, "weekly.png"))
    shutil.copy(filename_light, os.path.join(web_dir, "weekly_light.png"))
    shutil.copy(filename_en, os.path.join(web_dir, "weekly_en.png"))
    shutil.copy(filename_light_en, os.path.join(web_dir, "weekly_light_en.png"))
    
    up_h = stats['total_up'] / 3600
    down_h = stats['total_down'] / 3600
    plan_up_h = stats.get('total_plan_up', 0)
    
    total_h = up_h + down_h
    up_pct = (up_h / total_h * 100) if total_h > 0 else 0
    
    if up_pct > 90:
        verdict = "Тиждень був надзвичайно стабільним. Енергосистема працювала майже без обмежень."
    elif up_pct > 70:
        verdict = "Відносно спокійний тиждень. Відключення були прогнозованими та нетривалими."
    elif up_pct > 50:
        verdict = "Складний тиждень. Енергетики застосовували обмеження, але світло було більшу часть часу."
    else:
        verdict = "Важкий енергетичний тиждень. Тривалі відключення та дефіцит потужності в мережі."

    day_names = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця", "Субота", "Неділя"]
    best_day = stats['best_day']
    worst_day = stats['worst_day']
    easiest = stats.get('easiest_day')
    hardest = stats.get('hardest_day')

    plan_section = ""
    if plan_up_h > 0:
        def format_duration_h(hours_val):
            h = int(abs(hours_val))
            m = int(round((abs(hours_val) - h) * 60))
            if m == 60:
                h += 1
                m = 0
            parts = []
            if h > 0: parts.append(f"{h} г")
            if m > 0: parts.append(f"{m} хв")
            return " ".join(parts) if parts else "0 хв"

        diff_total = up_h - plan_up_h
        sign = "+" if diff_total > 0 else "-" if diff_total < 0 else ""
        diff_formatted = f"{sign}{format_duration_h(abs(diff_total))}"
        
        compliance_pct = (up_h / plan_up_h * 100) if plan_up_h > 0 else 0
        
        plan_section = f"""
📉 <b>План vs Факт:</b>
 • За планом 🔆 <b>{int(plan_up_h)}г</b>
 • Реально 🔆 <b>{int(up_h)}г</b>
 • Відхилення: <b>{diff_formatted}</b> (Світла {compliance_pct:.0f}% від плану)
"""
        if easiest and hardest and easiest != hardest:
             e_name = day_names[easiest['date'].weekday()]
             h_name = day_names[hardest['date'].weekday()]
             e_diff = easiest['diff']
             h_diff = hardest['diff']
             
             e_sign = "+" if e_diff > 0 else "-" if e_diff < 0 else ""
             h_sign = "+" if h_diff > 0 else "-" if h_diff < 0 else ""
             
             plan_section += f"\n🌤 <b>Легше ніж очікувалось:</b> {e_name} ({e_sign}{format_duration_h(abs(e_diff))} понад план)\n🌩 <b>Важче ніж очікувалось:</b> {h_name} ({h_sign}{format_duration_h(abs(h_diff))} від плану)"

    alerts_count, alerts_dur_sec, alerts_pct = get_weekly_alerts_stats(monday, sunday)
    alerts_h = alerts_dur_sec / 3600
    alerts_h_int = int(alerts_h)
    alerts_m_int = int((alerts_h % 1) * 60)

    caption = f"""📅 <b>Енергетичний тиждень ({monday.strftime('%d.%m')} - {sunday.strftime('%d.%m')})</b>

📊 <b>Загальні підсумки:</b>
 • Світло було 🔆 <b>{int(up_h)}г {int((up_h%1)*60)}хв</b> ({int(up_pct)}%)
 • Відключення ✖️ <b>{int(down_h)}г {int((down_h%1)*60)}хв</b>
 • В середньому без світла: <b>{int(down_h/7)}г {int(((down_h/7)%1)*60)}хв</b> на добу
 • Повітряні тривоги 🚨 <b>{alerts_count}</b> за тиждень (сумарно <b>{alerts_h_int}г {alerts_m_int}хв</b>, або <b>{alerts_pct:.1f}%</b> від усього часу)
{plan_section}

🏆 <b>Найменше відключень:</b> {day_names[best_day['date'].weekday()]}
🧟 <b>Найбільше відключень:</b> {day_names[worst_day['date'].weekday()]}

📝 <b>Аналіз:</b>
{verdict}

#тиждень #статистика_світла"""
    
    if not args.no_send:
        if get_quiet_status() == "quiet":
            print("Quiet mode active: Skipping weekly Telegram report.")
        else:
            send_telegram_photo(filename, caption)
    
    if os.path.exists(filename):
        os.remove(filename)
    if os.path.exists(filename_light):
        os.remove(filename_light)
    if os.path.exists(filename_en):
        os.remove(filename_en)
    if os.path.exists(filename_light_en):
        os.remove(filename_light_en)
