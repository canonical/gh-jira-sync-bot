import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

UNITTESTS_DIR = Path(__file__).parent
load_dotenv(UNITTESTS_DIR / "dumm_env", verbose=True)
assert os.environ["JIRA_INSTANCE"]

# import only after we set dummy environment
from github_jira_sync_app.main import app  # noqa: E402

client = TestClient(app)


def _get_json(file_name):
    with open(UNITTESTS_DIR / "payloads" / file_name) as file:
        return json.load(file)


def _post_new_issue(mock_github):
    label = type("Label", (), {"name": "bug"})()
    mock_github.issue.labels = [label]
    return client.post("/", json=_get_json("issue_labeled_correct.json"))


def test_new_issue_creation_disables_jira_prefetch(
    signature_mock, mock_github, mock_jira
):
    """Avoid Jira's automatic follow-up GET after a successful issue POST."""
    response = _post_new_issue(mock_github)

    assert response.status_code == 200
    assert "Issue was created in Jira" in response.json()["msg"]
    assert mock_jira.client.create_issue.call_count == 1
    assert mock_jira.client.create_issue.call_args.kwargs["prefetch"] is False


def test_duplicate_lookup_is_bounded(signature_mock, mock_github, mock_jira):
    """Fetch only the first Jira match and fields used by update paths."""
    response = _post_new_issue(mock_github)

    assert response.status_code == 200
    lookup = mock_jira.client.enhanced_search_issues.call_args
    assert lookup.kwargs["maxResults"] == 1
    assert lookup.kwargs["fields"] == "labels,components"
