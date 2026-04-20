import logging
import time

from fastapi import FastAPI
from fastapi import Response
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import Resource
from prometheus_client import make_asgi_app

logger = logging.getLogger("sync-bot-server")


class MetricsAndLoggingMiddleware:
    """Raw ASGI middleware for metrics collection and exception logging.

    Unlike BaseHTTPMiddleware, this actually catches exceptions that
    Starlette's ServerErrorMiddleware would otherwise swallow silently.
    """

    def __init__(self, app, request_counter, error_counter, duration_histogram):
        self.app = app
        self.request_counter = request_counter
        self.error_counter = error_counter
        self.duration_histogram = duration_histogram

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        self.request_counter.add(1)
        start_time = time.time()
        status_code = 500
        response_started = False

        async def send_wrapper(message):
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            logger.exception("Unhandled exception")
            self.error_counter.add(1)
            if not response_started:
                response = Response("Internal server error", status_code=500)
                await response(scope, receive, send)
        else:
            if status_code >= 500:
                self.error_counter.add(1)
        finally:
            duration = time.time() - start_time
            path = scope.get("path", "unknown")
            method = scope.get("method", "unknown")
            self.duration_histogram.record(
                duration,
                {"method": method, "path": path, "status_code": str(status_code)},
            )


def setup_metrics(app: FastAPI, service_name="sync-bot"):
    resource = Resource(attributes={SERVICE_NAME: service_name})

    prometheus_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(metric_readers=[prometheus_reader], resource=resource)
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter_provider().get_meter(service_name)

    request_counter = meter.create_counter(
        "syncbot_requests_total", description="Total number of sync bot requests"
    )

    error_counter = meter.create_counter(
        "syncbot_errors_total", description="Total number of internal errors"
    )

    test_counter = meter.create_counter(
        "syncbot_test_requests_total", description="Total number of visits to the test endpoint"
    )

    request_duration_histogram = meter.create_histogram(
        "syncbot_request_duration_seconds", unit="s", description="Histogram of request duration"
    )

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    app.add_middleware(
        MetricsAndLoggingMiddleware,
        request_counter=request_counter,
        error_counter=error_counter,
        duration_histogram=request_duration_histogram,
    )

    return {
        "meter": meter,
        "request_counter": request_counter,
        "error_counter": error_counter,
        "test_counter": test_counter,
        "duration_histogram": request_duration_histogram,
    }
