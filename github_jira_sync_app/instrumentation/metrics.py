import logging
import os
import time

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.resources import Resource
from prometheus_client import make_asgi_app


def define_logger():
    """Define logger to output to the file and to STDOUT."""
    log = logging.getLogger("sync-bot-server")
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s (%(levelname)s) %(message)s", datefmt="%d.%m.%Y %H:%M:%S"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    log_file = os.environ.get("SYNC_BOT_LOGFILE", "sync_bot.log")
    file_handler = logging.FileHandler(filename=log_file)
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    return log


logger = define_logger()


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

    app.middleware("http")(
        create_metrics_middleware(request_counter, error_counter, request_duration_histogram)
    )

    return {
        "meter": meter,
        "request_counter": request_counter,
        "error_counter": error_counter,
        "test_counter": test_counter,
        "duration_histogram": request_duration_histogram,
    }


def create_metrics_middleware(request_counter, error_counter, duration_histogram):
    async def metrics_middleware(request: Request, call_next):
        request_counter.add(1)
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception:
            error_counter.add(1)

            duration = time.time() - start_time
            duration_histogram.record(
                duration,
                {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": "500",
                },
            )
            return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

        if response.status_code == 500:
            error_counter.add(1)

        duration = time.time() - start_time
        duration_histogram.record(
            duration,
            {
                "method": request.method,
                "path": request.url.path,
                "status_code": str(response.status_code),
            },
        )

        return response

    return metrics_middleware
