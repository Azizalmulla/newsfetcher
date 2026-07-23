"""Observability stubs for Phase 0.

Sentry and OpenTelemetry activate only when configured via environment.
No-op otherwise so local development stays lightweight.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI

from app.core.config import Settings

logger = logging.getLogger(__name__)


def init_sentry(settings: Settings) -> None:
    if not settings.sentry_dsn:
        logger.info("Sentry disabled (SENTRY_DSN empty)")
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=0.1 if settings.app_env == "production" else 0.0,
        send_default_pii=False,
    )
    logger.info("Sentry initialized")


def init_otel(app: FastAPI, settings: Settings) -> None:
    if settings.otel_traces_exporter == "none" or not settings.otel_exporter_otlp_endpoint:
        logger.info("OpenTelemetry tracing disabled")
        return

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry FastAPI instrumentation enabled")


def redact_secrets(payload: dict[str, Any]) -> dict[str, Any]:
    """Utility for safe structured logging of config-like dicts."""
    sensitive = {"password", "secret", "token", "api_key", "dsn", "authorization"}
    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(part in lowered for part in sensitive):
            redacted[key] = "***"
        else:
            redacted[key] = value
    return redacted
