import asyncio
import signal

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


async def main():
    print("Starting Power-Safety-UA Background Services (Async)...", flush=True)
    await load_state()

    from app.light_service import get_air_raid_alert, state

    current_alert = get_air_raid_alert()
    print(
        f"Startup check: Status={state.get('status')}, Air Raid={current_alert.get('status')} ({current_alert.get('location')})",
        flush=True,
    )

    power_safety_info.info(
        {"version": get_version(), "language": "python", "role": "worker"}
    )

    loop = asyncio.get_running_loop()

    def _shutdown():
        print("Shutdown requested, stopping loops...", flush=True)
        asyncio.ensure_future(request_shutdown())

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    await asyncio.gather(
        monitor_loop(), alerts_loop(), schedule_loop(), metrics_collector_loop()
    )
    print("All loops stopped. Exiting.", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt. Exiting.", flush=True)
