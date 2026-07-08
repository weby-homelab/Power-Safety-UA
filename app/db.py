import structlog
import os
import aiosqlite
from app.config import settings
from app.metrics import event_log_errors

logger = structlog.get_logger(__name__)


DB_FILE = os.path.join(settings.data_dir, "power_safety.db")
_db_initialized = False


_SQLITE_PRAGMAS = """
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;
    PRAGMA busy_timeout=5000;
    PRAGMA foreign_keys=ON;
"""


async def init_db():
    global _db_initialized
    if _db_initialized:
        return
    os.makedirs(settings.data_dir, exist_ok=True)
    async with aiosqlite.connect(DB_FILE) as db:
        for pragma in _SQLITE_PRAGMAS.strip().split(";"):
            pragma = pragma.strip()
            if pragma:
                await db.execute(pragma)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event TEXT NOT NULL,
                date_str TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)
        """)
        await db.commit()
    _db_initialized = True
    logger.info("sqlite_initialized", db_file=DB_FILE, journal_mode="WAL")


async def vacuum_db():
    try:
        await init_db()
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            await db.execute("VACUUM")
            await db.commit()
        logger.info("sqlite_vacuum_completed")
    except Exception as e:
        logger.error(f"sqlite_vacuum_error: {e}")


async def log_event_db(event: str, timestamp: float, date_str: str):
    try:
        await init_db()
        async with aiosqlite.connect(DB_FILE, timeout=10) as db:
            await db.execute(
                "INSERT INTO events (timestamp, event, date_str) VALUES (?, ?, ?)",
                (timestamp, event, date_str),
            )
            await db.commit()
    except Exception as e:
        logger.error(f"sqlite_write_error: {e}")
        event_log_errors.inc()


async def get_events_db(limit: int = 1000):
    try:
        await init_db()
        async with aiosqlite.connect(DB_FILE, timeout=10) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT timestamp, event, date_str FROM events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        "timestamp": r["timestamp"],
                        "event": r["event"],
                        "date_str": r["date_str"],
                    }
                    for r in rows
                ][::-1]
    except Exception as e:
        logger.error(f"sqlite_read_error: {e}")
        return []
