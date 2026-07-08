import time
import asyncio
import pytest
from app.light_service import run_loop_with_backoff, is_loop_running, request_shutdown
from app.parser_service import CircuitBreaker, _is_private_host, has_schedule_changed


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        assert cb.can_execute() is True
        assert cb.state == "CLOSED"

    def test_opens_after_failures(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure()
        assert cb.state == "CLOSED"
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.can_execute() is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"
        assert cb.can_execute() is False

        time.sleep(0.1)
        assert cb.can_execute() is True
        assert cb.state == "HALF-OPEN"

    def test_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "OPEN"

        time.sleep(0.1)
        cb.record_success()
        assert cb.state == "CLOSED"
        assert cb.can_execute() is True


class TestScheduleChangeDetection:
    def test_no_change_on_same_data(self):
        old = {"yasno": {"GPV36": {"2026-07-08": {"slots": [True, False]}}}}
        new = {"yasno": {"GPV36": {"2026-07-08": {"slots": [True, False]}}}}
        assert has_schedule_changed(old, new) is False

    def test_detects_slot_change(self):
        old = {"yasno": {"GPV36": {"2026-07-08": {"slots": [True, False]}}}}
        new = {"yasno": {"GPV36": {"2026-07-08": {"slots": [False, False]}}}}
        assert has_schedule_changed(old, new) is True

    def test_no_old_data_no_change(self):
        old = {}
        new = {"yasno": {"GPV36": {"2026-07-08": {"slots": [True, False]}}}}
        assert has_schedule_changed(old, new) is False

    def test_new_source_not_in_old(self):
        old = {"yasno": {"GPV36": {"2026-07-08": {"slots": [True]}}}}
        new = {
            "yasno": {"GPV36": {"2026-07-08": {"slots": [True]}}},
            "github": {"GPV36": {"2026-07-08": {"slots": [False]}}},
        }
        assert has_schedule_changed(old, new) is False


class TestSSRFBlocklist:
    def test_localhost_blocked(self):
        assert _is_private_host("localhost") is True
        assert _is_private_host("127.0.0.1") is True

    def test_private_ranges_blocked(self):
        assert _is_private_host("10.0.0.1") is True
        assert _is_private_host("192.168.1.1") is True
        assert _is_private_host("172.16.0.1") is True
        assert _is_private_host("169.254.169.254") is True

    def test_public_domain_allowed(self):
        assert _is_private_host("example.com") is False
        assert _is_private_host("google.com") is False

    def test_public_ip_allowed(self):
        assert _is_private_host("8.8.8.8") is False


class TestLoopBackoff:
    def test_loop_running_initial(self):
        assert is_loop_running() is True

    def test_is_loop_running_after_request_shutdown(self):
        asyncio.run(request_shutdown())
        assert is_loop_running() is False
        from app.light_service import _loop_shutdown_event

        _loop_shutdown_event.set()
        assert is_loop_running() is True

    @pytest.mark.anyio
    async def test_run_loop_executes_once(self):
        from app.light_service import _loop_shutdown_event

        _loop_shutdown_event.set()
        attempt = [0]

        async def do_work():
            attempt[0] += 1
            await request_shutdown()

        await run_loop_with_backoff("test_simple", do_work, interval=0.01)
        assert attempt[0] == 1


class TestHealthEndpoints:
    def test_health_live(self):
        from app.main import app
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        with patch("scripts.bootstrap.perform_cold_start_if_needed"):
            client = TestClient(app)

        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_health_ready(self):
        from app.main import app
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        with patch("scripts.bootstrap.perform_cold_start_if_needed"):
            client = TestClient(app)

        resp = client.get("/health/ready")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ready"}

    def test_metrics_endpoint_has_new_metrics(self):
        from app.main import app
        from fastapi.testclient import TestClient
        from unittest.mock import patch

        with patch("scripts.bootstrap.perform_cold_start_if_needed"):
            client = TestClient(app)

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "power_http_requests_total" in resp.text
        assert "power_http_request_duration_seconds" in resp.text
        assert "power_loop_health" in resp.text
