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
from app.generate_daily_report import load_events, get_intervals_for_date, format_duration, KYIV_TZ, load_schedule_slots, get_quiet_status

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
        now = datetime.datetime.now(tz=KYIV_TZ)
        end = min(now, day_end)
        if start < end:
            intervals.append((start, end, True))
            
    return intervals


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

def generate_weekly_chart(end_date, daily_data, theme='dark'):
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
        fig, ax = plt.subplots(figsize=(10, 5.0), facecolor=bg_color)
        ax.set_facecolor(bg_color)
        
        # Colors
        color_map = {'up': fact_on_color, 'down': fact_off_color, 'unknown': fact_on_color}
        sched_map = {True: plan_on_color, False: plan_off_color} 
        
        y_labels = []
        y_ticks = []
        
        dummy_date = datetime.date(2000, 1, 1)
        
        for i, day_info in enumerate(daily_data):
            day_date = day_info['date']
            intervals = day_info['intervals']
            
            y_pos = 9 - i * 1.3
            
            day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
            label = f"{day_names[day_date.weekday()]} {day_date.strftime('%d.%m')}"
            y_labels.append(label)
            y_ticks.append(y_pos)
            
            # --- 1. Draw Actual Data (Top Strip) ---
            now_kyiv = datetime.datetime.now(KYIV_TZ)
            
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
                        ax.broken_barh([(start_num, duration_num)], (y_pos + 0.18, 0.36), facecolors=color, edgecolor='none')

            # --- Separator Lines ---

            ax.axhline(y=y_pos + 0.18, color=bg_color, linewidth=0.5, zorder=5)
            ax.axhline(y=y_pos - 0.18, color=bg_color, linewidth=0.5, zorder=5)


            # --- Hour Markers on the Bars (Background Color) ---
            hour_points = [mdates.date2num(datetime.datetime.combine(dummy_date, datetime.time(h, 0))) for h in range(1, 24)]
            ax.vlines(hour_points, y_pos - 0.54, y_pos + 0.54, colors=bg_color, linewidth=0.8, zorder=6)

            # --- 2. Draw Schedule Data (Bottom Strip) ---
            slots = get_schedule_slots(day_date)
            if slots:
                sched_intervals = slots_to_intervals(slots)
                for start_h, duration_h, is_on in sched_intervals:
                    s_date = datetime.datetime.combine(dummy_date, datetime.time.min) + datetime.timedelta(hours=start_h)
                    start_n = mdates.date2num(s_date)
                    duration_n = duration_h / 24.0
                    
                    color = sched_map.get(is_on, plan_off_color)
                    ax.broken_barh([(start_n, duration_n)], (y_pos - 0.18, 0.36), facecolors=color, edgecolor='none')


            # --- 3. Draw Alert Data (Bottom-most Strip) ---
            alert_on_color = '#ef4444' # Red for alerts
            alert_off_color = '#334155' if theme == 'dark' else '#cbd5e1'
            x_start_num = mdates.date2num(datetime.datetime.combine(dummy_date, datetime.time.min))
            x_end_num = mdates.date2num(datetime.datetime.combine(dummy_date, datetime.time.max))
            ax.broken_barh([(x_start_num, x_end_num - x_start_num)], (y_pos - 0.54, 0.36), facecolors=alert_off_color, edgecolor='none')
            
            alert_intervals = get_alert_intervals(day_date)
            for start, end, is_alert in alert_intervals:
                if is_alert:
                    d_start = datetime.datetime.combine(dummy_date, start.time())
                    d_end = datetime.datetime.combine(dummy_date, end.time())
                    
                    if end.time() == datetime.time.min and end != start:
                         d_end += datetime.timedelta(days=1)
                    elif d_end < d_start:
                         d_end += datetime.timedelta(days=1)
                        
                    start_num = mdates.date2num(d_start)
                    duration_num = mdates.date2num(d_end) - start_num
                    
                    if duration_num > 0:
                        ax.broken_barh([(start_num, duration_num)], (y_pos - 0.54, 0.36), facecolors=alert_on_color, edgecolor='none')


        # Formatting
        ax.set_ylim(-0.5, 10.5)
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
        
        ax.set_title(f"Енергетичний тиждень ({daily_data[0]['date'].strftime('%d.%m')} - {daily_data[-1]['date'].strftime('%d.%m')})", fontsize=14, color=text_color)
        
        import matplotlib.patches as mpatches
        green_patch = mpatches.Patch(color=fact_on_color, label='Світло є')
        red_patch = mpatches.Patch(color=fact_off_color, label='Світла немає')
        yellow_patch = mpatches.Patch(color=plan_on_color, label='Графік: Є')
        gray_patch = mpatches.Patch(color=plan_off_color, label='Графік: Немає')
        alert_patch = mpatches.Patch(color='#ef4444', label='Тривога')
        alert_off_patch = mpatches.Patch(color=('#334155' if theme == 'dark' else '#cbd5e1'), label='Немає тривог')

        legend = plt.legend(handles=[green_patch, red_patch, yellow_patch, gray_patch, alert_patch, alert_off_patch],
                   loc='upper center', bbox_to_anchor=(0.5, -0.1),
                   fancybox=False, frameon=False, shadow=False, ncol=3, fontsize='small')
        plt.setp(legend.get_texts(), color=text_color)
        
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.22)
        
        suffix = "_light" if theme == 'light' else ""
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

    now = datetime.datetime.now(KYIV_TZ)
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
        temp_filename = generate_weekly_chart(sunday, stats['daily_data'], theme='dark')
        temp_light = generate_weekly_chart(sunday, stats['daily_data'], theme='light')
        
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
            
        sys.exit(0)

    # Standard Telegram Flow
    filename = generate_weekly_chart(sunday, stats['daily_data'], theme='dark')
    filename_light = generate_weekly_chart(sunday, stats['daily_data'], theme='light')
    
    # Save copy for Web Dashboard
    web_dir = os.path.join(DATA_DIR, "static")
    if not os.path.exists(web_dir): os.makedirs(web_dir)
    shutil.copy(filename, os.path.join(web_dir, "weekly.png"))
    shutil.copy(filename_light, os.path.join(web_dir, "weekly_light.png"))
    
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

    caption = f"""📅 <b>Енергетичний тиждень ({monday.strftime('%d.%m')} - {sunday.strftime('%d.%m')})</b>

📊 <b>Загальні підсумки:</b>
 • Світло було 🔆 <b>{int(up_h)}г {int((up_h%1)*60)}хв</b> ({int(up_pct)}%)
 • Відключення ✖️ <b>{int(down_h)}г {int((down_h%1)*60)}хв</b>
 • В середньому без світла: <b>{int(down_h/7)}г {int(((down_h/7)%1)*60)}хв</b> на добу
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
