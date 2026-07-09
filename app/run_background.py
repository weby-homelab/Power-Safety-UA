import asyncio
import signal

import structlog

from scripts import bootstrap

bootstrap.perform_cold_start_if_needed()

from app._version import get_version  # noqa: E402
from app.light_service import (  # noqa: E402
    monitor_loop,
    schedule_loop,
    alerts_loop,
    load_state,
    metrics_collector_loop,
    request_shutdown,
)
from app.metrics import power_safety_info  # noqa: E402

logger = structlog.get_logger(__name__)


async def main():
    logger.info("Starting Power-Safety-UA Background Services (Async)...")
    await load_state()

    from app.light_service import get_air_raid_alert, state

    current_alert = get_air_raid_alert()
    logger.info(
        "startup_check",
        status=state.get("status"),
        alert_status=current_alert.get("status"),
        alert_location=current_alert.get("location"),
    )

    power_safety_info.info(
        {"version": get_version(), "language": "python", "role": "worker"}
    )

    loop = asyncio.get_running_loop()

    def _shutdown():
        logger.info("Shutdown requested, stopping loops...")
        asyncio.ensure_future(request_shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    await asyncio.gather(
        monitor_loop(), alerts_loop(), schedule_loop(), metrics_collector_loop()
    )
    logger.info("All loops stopped. Exiting.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Exiting.")
