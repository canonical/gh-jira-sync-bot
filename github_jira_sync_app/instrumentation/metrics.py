from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.metrics import set_meter_provider, get_meter_provider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import make_asgi_app
from fastapi import FastAPI

# Set up OpenTelemetry meter provider and Prometheus exporter
prometheus_reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[prometheus_reader])
set_meter_provider(provider)
meter = get_meter_provider().get_meter("sync-bot")

request_counter = meter.create_counter(
    "syncbot_requests_total", description="Total number of sync bot requests"
)

error_counter = meter.create_counter(
    "syncbot_errors_total", description="Total number of internal errors"
)

def add_metrics(app: FastAPI):
    """Mount the /metrics endpoint to the FastAPI app."""
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    
    test_counter = meter.create_counter(
        "syncbot_test_requests_total", description="Number of times the /test endpoint was called"
    )

    # TODO: delete this - for demo only
    @app.get("/test")
    async def test_endpoint():
        test_counter.add(1)
        return {"msg": "Test endpoint hit!"}

    return app