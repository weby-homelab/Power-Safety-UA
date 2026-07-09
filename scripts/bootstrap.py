import os
import json
import time
from datetime import datetime
import subprocess
import shutil

import structlog

logger = structlog.get_logger(__name__)

# Отримуємо директорії
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(APP_DIR, "data"))

def perform_cold_start_if_needed():
    event_file = os.path.join(DATA_DIR, "event_log.json")
    sched_file = os.path.join(DATA_DIR, "last_schedules.json")
    history_file = os.path.join(DATA_DIR, "schedule_history.json")
    config_file = os.path.join(DATA_DIR, "config.json")

    # Якщо дані вже є, це не перший старт
    if os.path.exists(event_file) and os.path.exists(sched_file):
        return

    # Атомарний захист від гонки при одночасному старті кількох контейнерів
    lock_file = os.path.join(DATA_DIR, ".bootstrap.lock")
    os.makedirs(DATA_DIR, exist_ok=True)

    created_lock = False
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd)
        created_lock = True
    except FileExistsError:
        logger.info("Initialization already in progress by another process. Waiting...")
        for _ in range(30):
            time.sleep(1)
            if os.path.exists(event_file) and os.path.exists(sched_file):
                return
        logger.warning("Timeout waiting for initialization. Continuing...")
        return
    except Exception as e:
        logger.error("Failed to create lock file", error=str(e))

    try:
        logger.info("Cold Start detected! Initializing database for current region...")
        
        # Створюємо потрібні папки
        os.makedirs(os.path.join(DATA_DIR, "static"), exist_ok=True)

        # Додаємо шляхи для імпортів
        import sys
        root_dir = os.path.dirname(APP_DIR)
        app_dir = os.path.join(root_dir, "app")
        if root_dir not in sys.path:
            sys.path.append(root_dir)
        if app_dir not in sys.path:
            sys.path.append(app_dir)

        # 1. Перевіряємо/Копіюємо config.json, якщо його немає
        if not os.path.exists(config_file):
            root_config = os.path.join(root_dir, "config.json")
            default_config = os.path.join(APP_DIR, "config.json")
            
            if os.path.exists(root_config):
                shutil.copy2(root_config, config_file)
                logger.info("Base config.json copied from project root.")
            elif os.path.exists(default_config):
                shutil.copy2(default_config, config_file)
                logger.info("Base config.json copied from scripts folder.")
            else:
                logger.info("Base config.json not found. Attempting auto-generation...")
                try:
                    from app.models import AppConfig
                    cfg = AppConfig()
                    with open(config_file, "w", encoding="utf-8") as f:
                        f.write(cfg.model_dump_json(indent=2))
                    logger.info("Default config.json auto-generated via AppConfig.")
                except Exception as e:
                    logger.error("Failed to import AppConfig, using fallback template", error=str(e))
                    fallback_config = {
                        "settings": {
                            "timezone": "Europe/Kyiv",
                            "region": "kyiv",
                            "push_interval": 30,
                            "safety_net_timeout": 35,
                            "admin_chat_id": "",
                            "telegram_bot_token": None,
                            "telegram_channel_id": None,
                            "groups": ["GPV36.1"],
                            "max_messages": 1,
                            "show_intervals_detail": False,
                            "style": "list",
                            "table_format": "code_lines"
                        },
                        "sources": {
                            "air_quality": {
                                "lat": "50.408",
                                "lon": "30.400",
                                "seb_station": "24185",
                                "location_name": "Борщагівка (Симиренка)"
                            },
                            "yasno": {
                                "enabled": True,
                                "name": "Yasno",
                                "dso_id": "902",
                                "region_id": "25"
                            },
                            "github": {
                                "enabled": True,
                                "name": "ДТЕК"
                            }
                        },
                        "advanced": {
                            "notifications": {
                                "report_times": ["06:00", "20:00"],
                                "mute_during_night": False,
                                "telegram_air_raid_alerts": True
                            },
                            "retention": {
                                "event_log_days": 7,
                                "schedule_history_days": 7
                            },
                            "data_sources": {
                                "priority": "github",
                                "custom_url": "",
                                "smart_deduplication": True,
                                "rollover_hour": 1
                            },
                            "dashboard": {
                                "show_aq": True,
                                "show_radiation": True,
                                "show_temp_graph": True,
                                "show_charts": True
                            },
                            "monitoring": {
                                "push_timeout": 35,
                                "push_interval_min": 20,
                                "push_interval_max": 65,
                                "safety_net_delay": 5
                            },
                            "quiet_mode": {
                                "stability_threshold_h": 24,
                                "auto_confirm": True
                            }
                        },
                        "ui": {}
                    }
                    with open(config_file, "w", encoding="utf-8") as f:
                        json.dump(fallback_config, f, indent=2, ensure_ascii=False)
                    logger.info("Default config.json written from fallback template.")

        # 2. Створюємо точку відліку (світло є прямо зараз)
        if not os.path.exists(event_file):
            now_ts = time.time()
            from zoneinfo import ZoneInfo
            now_dt = datetime.fromtimestamp(now_ts, tz=ZoneInfo("Europe/Kyiv"))
            
            start_event = [{
                "timestamp": now_ts,
                "event": "up",
                "date_str": now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "note": "Initial Startup"
            }]
            with open(event_file, "w", encoding="utf-8") as f:
                json.dump(start_event, f, indent=2, ensure_ascii=False)
            logger.info("event_log.json initialized.")

        # 3. Створюємо порожню історію графіків
        if not os.path.exists(history_file):
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump({}, f)
            logger.info("schedule_history.json initialized.")

        # 4. Примусово завантажуємо планові графіки на зараз
        if not os.path.exists(sched_file):
            try:
                from app.parser_service import update_local_schedules
                logger.info("Loading schedules according to config.json...")
                import asyncio
                asyncio.run(update_local_schedules(config_file, sched_file))
                logger.info("last_schedules.json generated successfully!")
            except Exception as e:
                logger.error("Error loading initial schedule", error=str(e))
                # Створюємо пустий файл, щоб не блокувати подальшу роботу
                with open(sched_file, "w", encoding="utf-8") as f:
                    json.dump({}, f)

        # 5. Примусово генеруємо картинки та статистику
        logger.info("Generating first dashboards...")
        try:
            subprocess.run(["python3", "app/generate_daily_report.py", "--no-send"], cwd=root_dir, check=True)
            subprocess.run(["python3", "app/generate_weekly_report.py", "--no-send"], cwd=root_dir, check=True)
            logger.info("Dashboards generated successfully.")
        except Exception as e:
            logger.error("Error generating initial dashboards", error=str(e))

    finally:
        if created_lock:
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    logger.info("Lock file removed successfully.")
            except Exception as e:
                logger.error("Error removing lock file", error=str(e))

    logger.info("Bootstrap initialization complete!")

if __name__ == "__main__":
    perform_cold_start_if_needed()
