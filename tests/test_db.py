import pytest
import os
from app.db import log_event_db, get_events_db, DB_FILE

@pytest.mark.anyio
async def test_db_operations():
    # Cleanup DB file if exists before test
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except:
            pass

    # Log mock events
    await log_event_db("up", 1700000000.0, "2023-11-14 22:13:20")
    await log_event_db("down", 1700003600.0, "2023-11-14 23:13:20")

    # Fetch events
    events = await get_events_db()
    
    assert len(events) == 2
    assert events[0]["event"] == "up"
    assert events[0]["timestamp"] == 1700000000.0
    assert events[1]["event"] == "down"
    assert events[1]["timestamp"] == 1700003600.0

    # Cleanup DB file after test
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except:
            pass
