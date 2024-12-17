import json
import os
from pathlib import Path

import responses
from dotenv import load_dotenv
from fastapi.testclient import TestClient

UNITTESTS_DIR = Path(__file__).parent
load_dotenv(Path(__file__).parent / "dumm_env", verbose=True)
assert os.environ["JIRA_INSTANCE"]

# import only after we set dummy environment
from github_jira_sync_app.main import app  # noqa: E402

client = TestClient(app)


def _get_json(file_name):
    with open(UNITTESTS_DIR / "payloads" / file_name) as file:
        return json.load(file)


def test_hash_validation():
    data_hash = "sha256=7127498186b8a9b282a54b72a954151d98681416693e07ea46e3a3eb960ddb42"
    response = client.post(
        "/",
        json=_get_json("comment_created_by_bot.json"),
        headers={"x-hub-signature-256": data_hash},
    )

    assert response.status_code == 200


def test_comment_created_by_bot(signature_mock):
    response = client.post(
        "/",
        json=_get_json("comment_created_by_bot.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Action was triggered by bot. Ignoring."}


@responses.activate(assert_all_requests_are_fired=True)
def test_comment_created_by_user(signature_mock):
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_existing_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_settings_with_labels.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_comment_created.yaml")
    response = client.post(
        "/",
        json=_get_json("comment_created_by_user.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "New comment from GitHub was added to Jira"}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_labeled_correct(signature_mock):
    """Test the scenario when an existing bug is labeled with the right label.

    Tests the following scenario:
        1. Authenticate in GitHub
        2. Get issue from GitHub
        3. Get content of .jira_sync_config.yaml from GitHub repo
        4. Ensure that the issue on GitHub is label with the approved label
        5. Authenticate in Jira
        6. Validate via JQL that this issue does not exist in Jira
        7. Create new issue in Jira
    """
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_no_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_settings_with_labels.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_create_issue.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_labeled_correct.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue was created in Jira. "}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_created_with_label(signature_mock):
    """Test the scenario when a bug is created on GitHub with the right label.

    Ensure that we skip the processing, see
    https://github.com/canonical/gh-jira-sync-bot/issues/57
    """
    response = client.post(
        "/",
        json=_get_json("issue_created_with_label.json"),
    )

    assert response.status_code == 200
    assert "Action was triggered by Issue Opened with Labels." in response.json()["msg"]


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_labeled_for_existing_ticket(signature_mock):
    """Test the scenario when a bug is labeled with the right label
    but the issue already exists in Jira.

    Tests the following scenario:
        1. Authenticate in GitHub
        2. Get issue from GitHub
        3. Get content of .jira_sync_config.yaml from GitHub repo
        4. Ensure that the issue on GitHub is label with the approved label
        5. Authenticate in Jira
        6. Validate via JQL that this issue does not exist in Jira but receive one issue back
        7. Do not perform any action
    """
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_existing_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_settings_with_labels.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_labeled_correct.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "No action performed"}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_created_without_label(signature_mock):
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_settings_with_labels.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_created_without_label.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue is not labeled with the specified label"}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_created_without_label_and_no_config(signature_mock):
    """Test when issue is created without a label and repo config doesn't require one.

    Tests the following scenario:
        1. Authenticate in GitHub
        2. Get issue from GitHub
        3. Get content of .jira_sync_config.yaml from GitHub repo
        4. Authenticate in Jira
        5. Validate via JQL that this issue does not exist in Jira
        6. Create new issue
    """
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_no_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")

    responses._add_from_file(
        UNITTESTS_DIR / "url_responses" / "github_settings_without_labels.yaml"
    )
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_create_issue.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_created_without_label.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue was created in Jira. "}


@responses.activate(assert_all_requests_are_fired=True)
def test_gh_comment_created(signature_mock):
    """Test when issue is created without a label and repo config doesn't require one.

    Tests the following scenario:
        1. Authenticate in GitHub
        2. Get issue from GitHub
        3. Get content of .jira_sync_config.yaml from GitHub repo
        4. Authenticate in Jira
        5. Validate via JQL that this issue does not exist in Jira
        6. Create new issue
        7. Add GitHub comment that issue is created
    """
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_no_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")

    responses._add_from_file(
        UNITTESTS_DIR / "url_responses" / "github_settings_with_gh_comment.yaml"
    )
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_create_issue.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_add_comment.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_with_too_long_description.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue was created in Jira. "}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_closed_as_completed(signature_mock):
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_existing_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_settings_with_labels.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_transition_issue.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_closed_as_completed.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Closed existing Jira Issue"}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_closed_as_not_planned(signature_mock):
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_jql_existing_issues.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_auth.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "github_settings_with_labels.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_transition_issue.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_closed_as_not_planned.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Closed existing Jira Issue as not planned"}
