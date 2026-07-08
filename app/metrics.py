from prometheus_client import Counter, Gauge, Histogram, Info
import structlog

logger = structlog.get_logger(__name__)

power_safety_info = Info("power_safety", "Power Safety UA version info")
active_sse_connections = Gauge(
    "power_safety_active_sse_connections",
    "Number of active SSE connections",
)
schedule_parsing_duration = Histogram(
    "power_safety_parsing_duration_seconds",
    "Time spent parsing schedules",
    buckets=(1, 2, 5, 10, 15, 30, 60, 120),
)

loop_restarts_total = Counter(
    "power_loop_restarts_total",
    "Total number of background loop restarts",
    ["loop_name"],
)

# Request metrics
http_requests_total = Counter(
    "power_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
http_request_duration = Histogram(
    "power_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

telegram_messages_total = Counter(
    "power_telegram_messages_total",
    "Total Telegram messages sent",
    ["type"],
)
telegram_errors_total = Counter(
    "power_telegram_errors_total",
    "Total Telegram API errors",
)

push_notifications_total = Counter(
    "power_push_notifications_total",
    "Total push notifications sent",
)

schedule_syncs_total = Counter(
    "power_schedule_syncs_total",
    "Total schedule sync operations",
    ["status"],
)
air_raid_alerts_total = Counter(
    "power_air_raid_alerts_total",
    "Total air raid alerts detected",
    ["status"],
)
loop_health = Gauge(
    "power_loop_health",
    "Health status of background loops (1=healthy, 0=down)",
    ["loop_name"],
)
state_save_errors = Counter(
    "power_state_save_errors_total",
    "Total state save errors",
)
event_log_errors = Counter(
    "power_event_log_errors_total",
    "Total event log errors",
)
