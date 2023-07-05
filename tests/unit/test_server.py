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
    data_hash = "sha256=38be3341f7b03bb234534be165ce4444d52bd95e798f547cabb1622db3628caa"
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
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "issue_labeled_correct.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "auth_github_responses.yaml")
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
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "issue_labeled_correct.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "auth_github_responses.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_labeled_correct.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue was created in Jira"}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_created_with_label(signature_mock):
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "issue_labeled_correct.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "auth_github_responses.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "jira_auth_responses.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_created_with_label.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue was created in Jira"}


@responses.activate(assert_all_requests_are_fired=True)
def test_issue_created_without_label(signature_mock):
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "issue_created_without_label.yaml")
    responses._add_from_file(UNITTESTS_DIR / "url_responses" / "auth_github_responses.yaml")
    response = client.post(
        "/",
        json=_get_json("issue_created_without_label.json"),
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Issue is not labeled with the specified label"}
