"""Centralized observability: structured logging + optional OpenTelemetry tracing.

This module is intentionally dependency-light at import time. The OpenTelemetry
libraries are imported lazily inside :func:`init_telemetry`, so the application
keeps running even when they are not installed (the default deployment).

Environment variables
----------------------
``LOG_FORMAT``   ``json`` (default, Loki/ELK friendly) or ``console`` (dev).
``LOG_LEVEL``    Standard Python logging level, e.g. ``INFO`` (default).
``OTEL_ENABLED`` ``true``/``1`` to enable distributed tracing.
``OTEL_EXPORTER_OTLP_ENDPOINT``
                OTLP/HTTP traces endpoint
                (default ``http://localhost:4318/v1/traces``).
``OTEL_SERVICE_NAME``
                Service name reported to the collector
                (default ``power-safety-ua``).
``ENVIRONMENT`` Deployment environment (default ``production``).
"""
from __future__ import annotations

import logging
import os
import time
import uuid

import structlog


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

def _log_level() -> int:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = logging.getLevelName(level_name)
    if not isinstance(level, int):
        return logging.INFO
    return level


def configure_structlog() -> None:
    """Configure structlog exactly once.

    Uses JSON output by default (one object per line, ideal for Loki/ELK) and
    merges per-request context variables so every log line can carry a
    ``request_id`` / ``trace_id``.
    """
    if getattr(configure_structlog, "_done", False):
        return
    log_format = os.environ.get("LOG_FORMAT", "json").lower()
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if log_format == "console":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_log_level()),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    configure_structlog._done = True  # type: ignore[attr-defined]


def get_logger(*args, **kwargs):
    return structlog.get_logger(*args, **kwargs)


# ---------------------------------------------------------------------------
# OpenTelemetry (optional, lazy)
# ---------------------------------------------------------------------------

_otel_ready = False


def _otel_active() -> bool:
    return os.environ.get("OTEL_ENABLED", "").lower() in ("1", "true", "yes")


def init_telemetry(service_name: str | None = None) -> None:
    """Initialise the OpenTelemetry tracer provider.

    No-op unless ``OTEL_ENABLED`` is set. Must be called once during
    application start-up (e.g. inside the FastAPI lifespan).
    """
    global _otel_ready
    if _otel_ready:
        return
    _otel_ready = True
    if not _otel_active():
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from app._version import get_version
    except ImportError:
        get_logger().warning("otel_disabled_missing_libs")
        return

    service = service_name or os.environ.get("OTEL_SERVICE_NAME", "power-safety-ua")
    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"
    )
    environment = os.environ.get("ENVIRONMENT", "production")
    try:
        version = get_version()
    except Exception:
        version = "unknown"

    resource = Resource.create(
        {
            "service.name": service,
            "service.version": version,
            "deployment.environment": environment,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    get_logger().info("otel_enabled", endpoint=endpoint, service=service)


def get_tracer():
    from opentelemetry import trace

    return trace.get_tracer("power-safety-ua")


# ---------------------------------------------------------------------------
# Request tracing middleware (raw ASGI — preserves SSE/streaming)
# ---------------------------------------------------------------------------

class RequestTracingMiddleware:
    """Binds a request id and (optionally) an OTel span to every HTTP request.

    Emits a structured ``request_handled`` access-log line. Because this is a
    raw ASGI middleware that only inspects ``http.response.start`` via a wrapped
    ``send``, it does not buffer the body and is therefore safe for the SSE
    (Server-Sent Events) endpoints used by the dashboard.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request

        request = Request(scope)
        request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex

        otel_span = None
        if _otel_active():
            try:
                tracer = get_tracer()
                otel_span = tracer.start_as_current_span(
                    f"{request.method} {request.url.path}"
                )
                otel_span.__enter__()
                from opentelemetry import trace as _trace

                span_ctx = _trace.get_current_span().get_span_context()
                if span_ctx and span_ctx.trace_id:
                    structlog.contextvars.bind_contextvars(
                        request_id=request_id,
                        trace_id=f"{span_ctx.trace_id:016x}",
                    )
                else:
                    structlog.contextvars.bind_contextvars(request_id=request_id)
            except Exception:
                otel_span = None
                structlog.contextvars.bind_contextvars(request_id=request_id)
        else:
            structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            get_logger("http.access").exception(
                "request_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            duration_ms = round((time.time() - start) * 1000, 2)
            get_logger("http.access").info(
                "request_handled",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=status_code,
                duration_ms=duration_ms,
            )
            if otel_span is not None:
                otel_span.__exit__(None, None, None)
            structlog.contextvars.clear_contextvars()
