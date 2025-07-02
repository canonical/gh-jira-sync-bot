from prometheus_client import make_asgi_app
from fastapi import FastAPI
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

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
    # Mount the /metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    return {
        "meter": meter,
        "request_counter": request_counter,
        "error_counter": error_counter,
        "test_counter": test_counter
    }