import os
from unittest.mock import patch

from app.light_service import update_worker_heartbeat


def test_update_worker_heartbeat_creates_file(tmp_path, monkeypatch):
    test_heartbeat_file = str(tmp_path / "worker_heartbeat")
    monkeypatch.setattr("app.light_service.WORKER_HEARTBEAT_FILE", test_heartbeat_file)
    monkeypatch.setattr("app.light_service._last_heartbeat_time", 0.0)

    assert not os.path.exists(test_heartbeat_file)
    update_worker_heartbeat(force=True)

    assert os.path.exists(test_heartbeat_file)
    with open(test_heartbeat_file, "r", encoding="utf-8") as f:
        content = f.read().strip()
    assert float(content) > 0


def test_update_worker_heartbeat_throttled(tmp_path, monkeypatch):
    test_heartbeat_file = str(tmp_path / "worker_heartbeat")
    monkeypatch.setattr("app.light_service.WORKER_HEARTBEAT_FILE", test_heartbeat_file)
    monkeypatch.setattr("app.light_service._last_heartbeat_time", 0.0)

    # First call writes file
    t0 = 1000.0
    with patch("time.time", return_value=t0):
        update_worker_heartbeat(force=True)

    with open(test_heartbeat_file, "r", encoding="utf-8") as f:
        assert float(f.read().strip()) == t0

    # Second call within 10s should be throttled (no write)
    t1 = 1010.0
    with patch("time.time", return_value=t1):
        update_worker_heartbeat(force=False)

    with open(test_heartbeat_file, "r", encoding="utf-8") as f:
        assert float(f.read().strip()) == t0

    # Third call after 16s should write
    t2 = 1016.0
    with patch("time.time", return_value=t2):
        update_worker_heartbeat(force=False)

    with open(test_heartbeat_file, "r", encoding="utf-8") as f:
        assert float(f.read().strip()) == t2


def test_update_worker_heartbeat_exception_resilient(monkeypatch):
    monkeypatch.setattr(
        "app.light_service.WORKER_HEARTBEAT_FILE", "/proc/invalid_path/heartbeat"
    )
    monkeypatch.setattr("app.light_service._last_heartbeat_time", 0.0)

    # Should not raise exception
    update_worker_heartbeat(force=True)
