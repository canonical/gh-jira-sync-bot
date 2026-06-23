import json
import os
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from dotenv import load_dotenv
from fastapi.testclient import TestClient
from github import GithubException

UNITTESTS_DIR = Path(__file__).parent
load_dotenv(Path(__file__).parent / "dumm_env", verbose=True)
assert os.environ["JIRA_INSTANCE"]

# import only after we set dummy environment
from github_jira_sync_app.main import app  # noqa: E402

client = TestClient(app)


def _get_json(file_name):
    with open(UNITTESTS_DIR / "payloads" / file_name) as file:
        return json.load(file)


def _make_label(name):
    """Create a mock PyGithub Label object."""
    label = MagicMock()
    label.name = name
    return label


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------
def test_hash_validation():
    data_hash = "sha256=7127498186b8a9b282a54b72a954151d98681416693e07ea46e3a3eb960ddb42"
    response = client.post(
        "/",
        json=_get_json("comment_created_by_bot.json"),
        headers={"x-hub-signature-256": data_hash},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Early exit branches (no GitHub/Jira interaction needed)
# ---------------------------------------------------------------------------
class TestEarlyExits:
    def test_missing_action_key(self, signature_mock):
        response = client.post("/", json={"issue": {}, "sender": {"login": "user"}})
        assert response.status_code == 200
        assert "wasn't triggered by Issue action" in response.json()["msg"]

    def test_missing_issue_key(self, signature_mock):
        response = client.post("/", json={"action": "opened", "sender": {"login": "user"}})
        assert response.status_code == 200
        assert "wasn't triggered by Issue action" in response.json()["msg"]

    def test_pr_comment_ignored(self, signature_mock):
        payload = _get_json("comment_created_by_user.json")
        payload["issue"]["pull_request"] = {"url": "https://api.github.com/repos/test/pulls/1"}
        response = client.post("/", json=payload)
        assert response.status_code == 200
        assert "PR comment" in response.json()["msg"]

    def test_bot_triggered_ignored(self, signature_mock):
        response = client.post("/", json=_get_json("comment_created_by_bot.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Action was triggered by bot. Ignoring."}

    def test_comment_deleted_ignored(self, signature_mock):
        payload = _get_json("comment_created_by_user.json")
        payload["action"] = "deleted"
        response = client.post("/", json=payload)
        assert response.status_code == 200
        assert "deleted" in response.json()["msg"]

    def test_comment_edited_ignored(self, signature_mock):
        payload = _get_json("comment_created_by_user.json")
        payload["action"] = "edited"
        response = client.post("/", json=payload)
        assert response.status_code == 200
        assert "edited" in response.json()["msg"]

    def test_unknown_issue_action_ignored(self, signature_mock):
        payload = _get_json("issue_created_without_label.json")
        payload["action"] = "transferred"
        response = client.post("/", json=payload)
        assert response.status_code == 200
        assert "transferred" in response.json()["msg"]

    def test_issue_opened_with_labels_skipped(self, signature_mock):
        response = client.post("/", json=_get_json("issue_created_with_label.json"))
        assert response.status_code == 200
        assert "Issue Opened with Labels" in response.json()["msg"]

    def test_issue_labeled_synced_to_jira_ignored(self, signature_mock):
        response = client.post("/", json=_get_json("issue_labeled_synced_to_jira.json"))
        assert response.status_code == 200
        assert "synced-to-jira" in response.json()["msg"]
        assert "Purposefully ignored" in response.json()["msg"]


# ---------------------------------------------------------------------------
# Config / validation branches (need GitHub mock)
# ---------------------------------------------------------------------------
class TestConfigValidation:
    def test_config_file_missing(self, signature_mock, mock_github):
        mock_github.repo.get_contents.side_effect = GithubException(404, "Not Found", None)
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "jira_sync_config.yaml file was not found" in response.json()["msg"]

    def test_config_file_invalid_yaml(self, signature_mock, mock_github):
        contents = MagicMock()
        contents.decoded_content = b"settings:\n  bad: yaml: indentation: ["
        mock_github.repo.get_contents.return_value = contents
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "invalid" in response.json()["msg"].lower()

    def test_config_file_empty(self, signature_mock, mock_github):
        """An empty .jira_sync_config.yaml should be handled gracefully (no 500).

        Reproduces the crash from crash.json: an `edited` webhook on a repo whose
        config file is empty. ``yaml.safe_load("")`` returns ``None`` which used to
        blow up ``merge_dicts`` with a ``TypeError`` (HTTP 500).
        """
        contents = MagicMock()
        contents.decoded_content = b""
        mock_github.repo.get_contents.return_value = contents
        response = client.post("/", json=_get_json("issue_edited.json"))
        assert response.status_code == 200
        assert "empty" in response.json()["msg"].lower()

    def test_missing_jira_project_key(self, signature_mock, mock_github):
        mock_github.set_config(
            {
                "settings": {
                    "jira_project_key": None,
                    "status_mapping": {"opened": "To Do", "closed": "Done"},
                    "labels": None,
                    "components": None,
                    "sync_description": True,
                    "sync_comments": True,
                    "add_gh_comment": False,
                    "add_gh_synced_label": False,
                    "epic_key": None,
                    "label_mapping": None,
                    "summary": None,
                }
            }
        )
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "Jira project key" in response.json()["msg"]

    def test_missing_status_mapping(self, signature_mock, mock_github):
        mock_github.set_config(
            {
                "settings": {
                    "jira_project_key": "TEST",
                    "status_mapping": None,
                    "labels": None,
                    "components": None,
                    "sync_description": True,
                    "sync_comments": True,
                    "add_gh_comment": False,
                    "add_gh_synced_label": False,
                    "epic_key": None,
                    "label_mapping": None,
                    "summary": None,
                }
            }
        )
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "Status mapping" in response.json()["msg"]

    def test_issue_not_labeled_with_allowed_label(self, signature_mock, mock_github):
        mock_github.issue.labels = [_make_label("enhancement")]
        mock_github.set_config()  # default config requires "bug" label
        response = client.post("/", json=_get_json("issue_created_without_label.json"))
        assert response.status_code == 200
        assert "not labeled with the specified label" in response.json()["msg"]


# ---------------------------------------------------------------------------
# No existing Jira issue - create new
# ---------------------------------------------------------------------------
class TestCreateNewJiraIssue:
    def test_create_from_labeled(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "Issue was created in Jira" in response.json()["msg"]
        mock_jira.client.create_issue.assert_called_once()

    def test_create_from_opened_without_label_config(self, signature_mock, mock_github, mock_jira):
        """When no labels are required, opened issue (without labels) should sync."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(labels=None)
        mock_github.set_config(settings)
        mock_github.issue.labels = []
        response = client.post("/", json=_get_json("issue_created_without_label.json"))
        assert response.status_code == 200
        assert "Issue was created in Jira" in response.json()["msg"]

    def test_create_with_epic_key(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(epic_key="EPIC-1")
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        call_kwargs = mock_jira.client.create_issue.call_args
        fields = call_kwargs[1]["fields"]
        assert fields["parent"] == {"key": "EPIC-1"}

    def test_create_with_components(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(components=["Frontend", "Backend"])
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        # Only "Frontend" exists in project
        frontend_comp = MagicMock()
        frontend_comp.name = "Frontend"
        mock_jira.client.project_components.return_value = [frontend_comp]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        call_kwargs = mock_jira.client.create_issue.call_args
        fields = call_kwargs[1]["fields"]
        assert fields["components"] == [{"name": "Frontend"}]

    def test_create_with_label_mapping(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(label_mapping={"bug": "Defect", "feature": "Story"})
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        call_kwargs = mock_jira.client.create_issue.call_args
        fields = call_kwargs[1]["fields"]
        assert fields["issuetype"] == {"name": "Defect"}

    def test_create_with_custom_summary(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(summary="[{issue.repository.name}] {issue.title}")
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        mock_jira.client.create_issue.assert_called_once()

    def test_create_with_synced_label(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(add_gh_synced_label=True)
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        mock_github.issue.add_to_labels.assert_called_once_with("synced-to-jira")

    def test_create_with_gh_comment(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(add_gh_comment=True)
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        mock_github.issue.create_comment.assert_called_once()
        comment_body = mock_github.issue.create_comment.call_args[0][0]
        assert "TEST-1" in comment_body or "jira" in comment_body.lower()

    def test_close_nonexistent_jira_issue_ignored(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        response = client.post("/", json=_get_json("issue_closed_as_completed.json"))
        assert response.status_code == 200
        assert "doesn't exist" in response.json()["msg"]
        mock_jira.client.create_issue.assert_not_called()


# ---------------------------------------------------------------------------
# Existing Jira issue
# ---------------------------------------------------------------------------
class TestExistingJiraIssue:
    def test_close_as_completed(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("issue_closed_as_completed.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Closed existing Jira Issue"}
        mock_jira.client.transition_issue.assert_called_once_with(mock_jira.existing_issue, "Done")

    def test_close_as_not_planned(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("issue_closed_as_not_planned.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Closed existing Jira Issue as not planned"}
        mock_jira.client.transition_issue.assert_called_once_with(
            mock_jira.existing_issue, "Rejected"
        )

    def test_reopen_existing_issue(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("issue_reopened.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Reopened existing Jira Issue"}
        mock_jira.client.transition_issue.assert_called_once_with(mock_jira.existing_issue, "To Do")

    def test_edit_existing_issue(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("issue_edited.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Updated existing Jira Issue"}
        mock_jira.existing_issue.update.assert_called_once()

    def test_edit_existing_issue_appends_components(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(components=["Frontend"])
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]

        # Existing issue already has "Backend" component
        existing = MagicMock()
        existing.key = "TEST-99"
        backend_comp = MagicMock()
        backend_comp.name = "Backend"
        existing.fields.components = [backend_comp]
        mock_jira.client.enhanced_search_issues.return_value = [existing]

        # "Frontend" is an allowed component in the project
        frontend_comp = MagicMock()
        frontend_comp.name = "Frontend"
        mock_jira.client.project_components.return_value = [frontend_comp]

        response = client.post("/", json=_get_json("issue_edited.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Updated existing Jira Issue"}
        call_kwargs = existing.update.call_args[1]["fields"]
        component_names = [c["name"] for c in call_kwargs["components"]]
        assert "Frontend" in component_names
        assert "Backend" in component_names

    def test_labeled_existing_no_action(self, signature_mock, mock_github, mock_jira):
        """Labeled with existing Jira issue, no comment → No action performed."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_comments=False)
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "No action performed"}


# ---------------------------------------------------------------------------
# Comment sync
# ---------------------------------------------------------------------------
class TestCommentSync:
    def test_comment_synced_to_existing_jira(self, signature_mock, mock_github, mock_jira):
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("comment_created_by_user.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "New comment from GitHub was added to Jira"}
        mock_jira.client.add_comment.assert_called_once()

    def test_comment_on_new_issue_creates_then_comments(
        self, signature_mock, mock_github, mock_jira
    ):
        """Comment created on issue not yet in Jira → create issue + sync comment."""
        mock_github.issue.labels = [_make_label("bug")]
        # No existing issues (default)
        response = client.post("/", json=_get_json("comment_created_by_user.json"))
        assert response.status_code == 200
        assert "Issue was created in Jira" in response.json()["msg"]
        assert "New comment from GitHub was added to Jira" in response.json()["msg"]
        mock_jira.client.create_issue.assert_called_once()
        mock_jira.client.add_comment.assert_called_once()

    def test_comment_sync_disabled(self, signature_mock, mock_github, mock_jira):
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_comments=False)
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("comment_created_by_user.json"))
        assert response.status_code == 200
        mock_jira.client.add_comment.assert_not_called()
        assert response.json() == {"msg": "No action performed"}

    def test_description_sync_disabled(self, signature_mock, mock_github, mock_jira):
        """When sync_description is False, issue body should not be in Jira description."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_description=False)
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        mock_github.issue.body = "Some body that should not appear"
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        call_kwargs = mock_jira.client.create_issue.call_args
        fields = call_kwargs[1]["fields"]
        assert "Some body that should not appear" not in fields["description"]


# ---------------------------------------------------------------------------
# Synced label + subsequent webhook flow
# ---------------------------------------------------------------------------
class TestSyncedLabelFlow:
    def test_issue_created_and_synced_label_webhook_ignored(
        self, signature_mock, mock_github, mock_jira
    ):
        """Create issue with synced label → next webhook for that label is ignored."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(add_gh_synced_label=True, labels=None)
        mock_github.set_config(settings)
        mock_github.issue.labels = []

        response = client.post("/", json=_get_json("issue_created_without_label.json"))
        assert response.status_code == 200
        assert "Issue was created in Jira" in response.json()["msg"]
        mock_github.issue.add_to_labels.assert_called_once_with("synced-to-jira")

        # Subsequent synced-to-jira label webhook is ignored (early exit, no mocks needed)
        response = client.post("/", json=_get_json("issue_labeled_synced_to_jira.json"))
        assert response.status_code == 200
        assert "Purposefully ignored" in response.json()["msg"]

    def test_sync_unlabelled_for_existing_issue(self, signature_mock, mock_github, mock_jira):
        """Test syncing removed labels for existing issue."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_labels=True, labels=["bug"])
        mock_github.set_config(settings)
        # "enhancement" is NOT in allowed labels ["bug"]
        mock_github.issue.labels = []
        mock_jira.set_existing_issues()
        mock_jira.existing_issue.fields.labels = ["foo"]
        response = client.post("/", json=_get_json("issue_unlabeled.json"))
        assert response.status_code == 200
        assert "Updated existing Jira Issue labels (foo -> None)" in response.json()["msg"]
        mock_jira.client.create_issue.assert_not_called()

    def test_sync_labels_for_existing_issue(self, signature_mock, mock_github, mock_jira):
        """Test syncing labels for existing issue."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_labels=True, labels=["bug"])
        mock_github.set_config(settings)
        # "enhancement" is NOT in allowed labels ["bug"]
        mock_github.issue.labels = [_make_label("enhancement")]
        mock_jira.set_existing_issues()
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "Updated existing Jira Issue labels (None -> enhancement)" in response.json()["msg"]
        mock_jira.client.create_issue.assert_not_called()

    def test_sync_labels_not_creates_issue_for_non_allowed_labels(
        self, signature_mock, mock_github, mock_jira
    ):
        """Ensure sync_labels=True does not bypass allowed-labels gate and create a Jira issue
        even when the issue only carries a label not in the allowed list.
        """
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_labels=True, labels=["bug"])
        mock_github.set_config(settings)
        # "enhancement" is NOT in allowed labels ["bug"]
        mock_github.issue.labels = [_make_label("enhancement")]
        # no existing Jira issue (default mock)
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert (
            "Issue in Jira doesn't exist and GitHub labels not found in allowed_labels. Ignoring."
            in response.json()["msg"]
        )
        mock_jira.client.create_issue.assert_not_called()

    def test_sync_labels_with_no_allowed_labels_creates_issue(
        self, signature_mock, mock_github, mock_jira
    ):
        """sync_labels=True with labels=None should still create a Jira issue on a label
        event when no allowed-labels filtering is configured.
        """
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_labels=True, labels=None)
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("enhancement")]
        # no existing Jira issue (default mock)
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "Issue was created in Jira" in response.json()["msg"]
        mock_jira.client.create_issue.assert_called_once()

    def test_sync_labels_no_change_required(self, signature_mock, mock_github, mock_jira):
        """When Jira and GitHub labels are already identical, no update should happen."""
        from tests.unit.conftest import _default_settings

        settings = _default_settings(sync_labels=True, labels=["bug"])
        mock_github.set_config(settings)
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        mock_jira.existing_issue.fields.labels = ["bug"]
        response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "No change to Jira Issue labels required"}
        mock_jira.existing_issue.update.assert_not_called()


# ---------------------------------------------------------------------------
# Redis deduplication
# ---------------------------------------------------------------------------
class TestRedisDedup:
    def test_redis_dedup_allows_first_request(self, signature_mock, mock_github, mock_jira):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = True  # first request gets the lock
        mock_github.issue.labels = [_make_label("bug")]
        with patch("github_jira_sync_app.main.redis_client", mock_redis):
            response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "Issue was created in Jira" in response.json()["msg"]
        mock_redis.setnx.assert_called_once()
        mock_redis.expire.assert_called_once()
        mock_redis.delete.assert_not_called()

    def test_redis_dedup_rejects_duplicate(self, signature_mock, mock_github, mock_jira):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = False  # duplicate
        mock_github.issue.labels = [_make_label("bug")]
        with patch("github_jira_sync_app.main.redis_client", mock_redis):
            response = client.post("/", json=_get_json("issue_labeled_correct.json"))
        assert response.status_code == 200
        assert "already being processed" in response.json()["msg"]
        mock_jira.client.create_issue.assert_not_called()

    def test_redis_dedup_cleanup_on_existing_issue(self, signature_mock, mock_github, mock_jira):
        mock_redis = MagicMock()
        mock_redis.setnx.return_value = True
        mock_github.issue.labels = [_make_label("bug")]
        mock_jira.set_existing_issues()
        with patch("github_jira_sync_app.main.redis_client", mock_redis):
            response = client.post("/", json=_get_json("issue_closed_as_completed.json"))
        assert response.status_code == 200
        assert response.json() == {"msg": "Closed existing Jira Issue"}
        mock_redis.delete.assert_not_called()
