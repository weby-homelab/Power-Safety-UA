import os

DATA_DIR = os.environ.get("DATA_DIR", "data")
STATE_FILE = os.path.join(DATA_DIR, "power_monitor_state.json")
EVENT_LOG_FILE = os.path.join(DATA_DIR, "event_log.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
SCHEDULES_FILE = os.path.join(DATA_DIR, "last_schedules.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
