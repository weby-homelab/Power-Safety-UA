import json
import os
import asyncio
import aiofiles
import fcntl
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class StorageUtils:
    """Helper methods for safe file operations."""

    @staticmethod
    async def load_json_async(path: str, default: Any = None) -> Any:
        if not os.path.exists(path):
            return default if default is not None else {}
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
                return (
                    json.loads(content)
                    if content
                    else (default if default is not None else {})
                )
        except Exception as e:
            logger.error("Error loading async", path=path, error=str(e))
            return default if default is not None else {}

    @staticmethod
    async def save_json_async(path: str, data: Any) -> bool:
        temp_path = f"{path}.tmp"
        try:
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))

            def _replace():
                os.chmod(temp_path, 0o600)
                os.replace(temp_path, path)

            await asyncio.to_thread(_replace)
            return True
        except Exception as e:
            logger.error("Error saving async", path=path, error=str(e))
            return False

    @staticmethod
    def load_json_sync(path: str, default: Any = None) -> Any:
        if not os.path.exists(path):
            return default if default is not None else {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Error loading sync", path=path, error=str(e))
            return default if default is not None else {}

    @staticmethod
    def save_json_sync(path: str, data: Any) -> bool:
        temp_path = f"{path}.tmp"
        try:
            os.makedirs(os.path.dirname(temp_path) or ".", mode=0o700, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, path)
            return True
        except Exception as e:
            logger.error("Error saving sync", path=path, error=str(e))
            return False


class SafeStateContextAsync:
    def __init__(self, file_lock_path: str):
        self._lock = asyncio.Lock()
        self._counter = 0
        self._owner = None
        self._flock_file = None
        self.file_lock_path = file_lock_path

    async def __aenter__(self):
        task = asyncio.current_task()
        if self._owner == task:
            self._counter += 1
            return self

        await self._lock.acquire()
        self._owner = task
        self._counter = 1
        try:

            def _acquire():
                self._flock_file = open(self.file_lock_path, "a")
                fcntl.flock(self._flock_file, fcntl.LOCK_EX)

            await asyncio.to_thread(_acquire)
        except Exception as e:
            logger.error("Error acquiring file lock", error=str(e))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owner != asyncio.current_task():
            return

        if self._counter > 1:
            self._counter -= 1
            return

        try:
            if self._flock_file:

                def _release():
                    try:
                        fcntl.flock(self._flock_file, fcntl.LOCK_UN)
                        self._flock_file.close()
                    except Exception:
                        pass

                await asyncio.to_thread(_release)
                self._flock_file = None
        finally:
            self._counter = 0
            self._owner = None
            self._lock.release()
