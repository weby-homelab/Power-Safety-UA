import asyncio
import sys

# Запуск ініціалізації для нових користувачів
from scripts import bootstrap
bootstrap.perform_cold_start_if_needed()

from app.light_service import monitor_loop, schedule_loop, alerts_loop, load_state, metrics_collector_loop

async def main():
    print("Starting Power-Safety-UA Background Services (Async)...", flush=True)
    await load_state()
    
    # Run all loops concurrently
    from app.light_service import get_air_raid_alert, state
    current_alert = get_air_raid_alert()
    print(f"Startup check: Status={state.get('status')}, Air Raid={current_alert.get('status')} ({current_alert.get('location')})", flush=True)
    
    await asyncio.gather(
        monitor_loop(),
        alerts_loop(),
        schedule_loop(),
        metrics_collector_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
