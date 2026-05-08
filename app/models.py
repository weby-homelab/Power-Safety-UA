from pydantic import BaseModel, Field, RootModel, ConfigDict
from typing import Dict, List, Optional, Any, Union
import os

class AppSettings(BaseModel):
    model_config = ConfigDict(extra='ignore')
    timezone: str = "Europe/Kyiv"
    region: str = "kyiv"
    push_interval: int = 30
    safety_net_timeout: int = 35
    admin_chat_id: str = Field(default_factory=lambda: os.environ.get("ADMIN_CHAT_ID", ""))
    telegram_bot_token: Optional[str] = None
    telegram_channel_id: Optional[str] = None
    groups: List[str] = ["GPV36.1"]
    max_messages: int = 1
    show_intervals_detail: bool = False
    style: str = "list"
    table_format: str = "code_lines"

class Notifications(BaseModel):
    model_config = ConfigDict(extra='ignore')
    report_times: List[str] = ["06:00", "20:00"]
    mute_during_night: bool = False
    telegram_air_raid_alerts: bool = True

class SourcesConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    air_quality: Dict[str, Any] = {"lat": "50.408", "lon": "30.400", "seb_station": "24185", "location_name": "Борщагівка (Симиренка)"}
    yasno: Dict[str, Any] = {"enabled": True, "name": "Yasno", "dso_id": "902", "region_id": "25"}
    github: Dict[str, Any] = {"enabled": True, "name": "ДТЕК"}

class AdvancedSettings(BaseModel):
    model_config = ConfigDict(extra='ignore')
    notifications: Notifications = Notifications()
    retention: Dict[str, int] = {"event_log_days": 7, "schedule_history_days": 7}
    data_sources: Dict[str, Any] = {"priority": "github", "custom_url": "", "smart_deduplication": True, "rollover_hour": 1}
    dashboard: Dict[str, bool] = {"show_aq": True, "show_radiation": True, "show_temp_graph": True, "show_charts": True}
    monitoring: Dict[str, Any] = {"push_timeout": 35, "push_interval_min": 20, "push_interval_max": 65, "safety_net_delay": 5}
    quiet_mode: Dict[str, Any] = {"stability_threshold_h": 24, "auto_confirm": True}

class AppConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    settings: AppSettings = AppSettings()
    sources: SourcesConfig = SourcesConfig()
    advanced: AdvancedSettings = AdvancedSettings()
    ui: Dict[str, Any] = {}

class AppState(BaseModel):
    model_config = ConfigDict(extra='ignore')
    status: str = "unknown"
    last_seen: float = 0.0
    went_down_at: float = 0.0
    came_up_at: float = 0.0
    secret_key: Optional[str] = None
    alert_status: str = "clear"
    quiet_mode: str = "auto"
    quiet_status: str = "active"
    pending_confirmation: bool = False
    safety_net_pending: bool = False
    safety_net_sent_at: float = 0.0
    safety_net_triggered_for: float = 0.0
    muted_until: float = 0.0
    stability_start: float = 0.0
    admin_token: Optional[str] = None
    last_schedule_hash: Optional[str] = None
    alert_start_time: Optional[float] = None

class ScheduleDay(BaseModel):
    model_config = ConfigDict(extra='ignore')
    status: str = "unknown"
    slots: Optional[List[Union[bool, None]]] = None

class ScheduleGroup(RootModel):
    root: Dict[str, ScheduleDay]

class SchedulesData(BaseModel):
    model_config = ConfigDict(extra='ignore')
    yasno: Optional[Dict[str, Dict[str, ScheduleDay]]] = None
    github: Optional[Dict[str, Dict[str, ScheduleDay]]] = None
