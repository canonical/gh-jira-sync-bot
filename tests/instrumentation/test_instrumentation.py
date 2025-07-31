from fastapi import FastAPI
from fastapi import Response
from prometheus_client.parser import text_string_to_metric_families
from starlette.testclient import TestClient

from github_jira_sync_app.instrumentation.metrics import setup_metrics


def create_test_app():
    app = FastAPI()

    metrics_instruments = setup_metrics(app)

    @app.get("/test")
    async def test_endpoint():
        metrics_instruments["test_counter"].add(1)
        return {"msg": "Test endpoint hit!"}

    @app.get("/error")
    async def error_endpoint():
        return Response(status_code=500)

    return app


def get_metric_value(metric_text: str, metric_name: str) -> float:
    for family in text_string_to_metric_families(metric_text):
        for sample in family.samples:
            if sample.name == metric_name:
                return sample.value
    return 0.0


def test_metrics_and_endpoints():
    app = create_test_app()
    client = TestClient(app)

    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"msg": "Test endpoint hit!"}

    error_response = client.get("/error")
    assert error_response.status_code == 500

    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_body = metrics_response.text

    total_requests_metric_name = "syncbot_requests_total"
    total_requests_value = get_metric_value(metrics_body, total_requests_metric_name)
    assert (
        total_requests_value >= 1
    ), f"Expected {total_requests_metric_name} to be >= 1, got {total_requests_value}"

    total_errors_metric_name = "syncbot_errors_total"
    total_errors_value = get_metric_value(metrics_body, total_errors_metric_name)
    assert (
        total_errors_value == 1
    ), f"Expected {total_errors_metric_name} to be == 1, got {total_errors_value}"
