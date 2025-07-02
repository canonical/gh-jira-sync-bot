from fastapi import FastAPI
from starlette.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families
from github_jira_sync_app.instrumentation.metrics import setup_metrics
from github_jira_sync_app.instrumentation.tracing import setup_tracing

def create_test_app():
    app = FastAPI()
    
    # Set up the metrics and tracing
    metrics_instruments = setup_metrics(app)
    setup_tracing(app)
    
    # Define the /test endpoint in the test app
    @app.get("/test")
    async def test_endpoint():
        # Increment the request counter for this endpoint
        metrics_instruments["test_counter"].add(1)
        return {"msg": "Test endpoint hit!"}

    return app

def get_metric_value(metric_text: str, metric_name: str) -> float:
    for family in text_string_to_metric_families(metric_text):
        for sample in family.samples:
            if sample.name == metric_name:
                return sample.value
    return 0.0

def test_metrics_and_test_endpoints():
    # Create the test app with metrics and tracing
    app = create_test_app()
    client = TestClient(app)

    # Hit /test to trigger counter increment
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"msg": "Test endpoint hit!"}

    # Hit /metrics to scrape Prometheus metrics
    metrics_response = client.get("/metrics")
    assert metrics_response.status_code == 200
    metrics_body = metrics_response.text

    # Check the test counter is present and greater than or equal to 1
    metric_name = "syncbot_test_requests_total"
    value = get_metric_value(metrics_body, metric_name)

    assert value >= 1, f"Expected {metric_name} to be >= 1, got {value}"
