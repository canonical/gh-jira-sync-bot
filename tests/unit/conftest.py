from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture(scope="session")
def signature_mock(request):
    """Bypass webhook signature verification while asserting it was called."""
    with patch("github_jira_sync_app.main.verify_signature", wraps=lambda *x: None) as signature:
        yield signature
        signature.assert_called()


def _default_settings(**overrides):
    """Build a valid repo settings dict with sane defaults, applying overrides."""
    settings = {
        "settings": {
            "components": None,
            "labels": ["bug"],
            "add_gh_comment": False,
            "add_gh_synced_label": False,
            "sync_description": True,
            "sync_comments": True,
            "epic_key": None,
            "jira_project_key": "TEST",
            "label_mapping": None,
            "status_mapping": {
                "opened": "To Do",
                "closed": "Done",
                "not_planned": "Rejected",
            },
            "summary": None,
        }
    }
    settings["settings"].update(overrides)
    return settings


@pytest.fixture()
def mock_github():
    """Patch GithubIntegration and Github at the library level.

    Returns a context object with:
      - git_integration: mocked GithubIntegration instance
      - github_client: mocked Github instance
      - repo: mocked Repository returned by git_connection
      - issue: mocked Issue object
      - set_config(settings_dict): sets the repo config YAML that get_contents returns
    """
    with (
        patch("github_jira_sync_app.main.git_integration") as mock_integration,
        patch("github_jira_sync_app.main.Github") as MockGithub,
        patch("github_jira_sync_app.main.Repository") as MockRepo,
        patch("github_jira_sync_app.main.Issue") as MockIssue,
    ):
        # GithubIntegration: get_repo_installation -> installation with .id
        installation = MagicMock()
        installation.id = 12345
        mock_integration.get_repo_installation.return_value = installation

        # GithubIntegration: get_access_token -> token object
        token = MagicMock()
        token.token = "ghs_fake_token"
        mock_integration.get_access_token.return_value = token

        # Github client
        github_client = MagicMock()
        MockGithub.return_value = github_client

        # Repository
        repo = MagicMock()
        MockRepo.return_value = repo

        # Issue
        issue = MagicMock()
        issue.html_url = "https://github.com/beliaev-maksim/test-ci/issues/30"
        issue.title = "day after"
        issue.body = "Issue body content"
        issue.user.login = "beliaev-maksim"
        MockIssue.return_value = issue

        ctx = MagicMock()
        ctx.integration = mock_integration
        ctx.github_client = github_client
        ctx.repo = repo
        ctx.issue = issue

        def set_config(settings_dict=None):
            if settings_dict is None:
                settings_dict = _default_settings()
            contents = MagicMock()
            contents.decoded_content = yaml.dump(settings_dict).encode()
            repo.get_contents.return_value = contents

        ctx.set_config = set_config
        # Apply default config
        set_config()

        yield ctx


@pytest.fixture()
def mock_jira():
    """Patch the JIRA client at the library level.

    Returns a context object with:
      - client: mocked JIRA instance
      - set_existing_issues(issues): configure JQL search results
    """
    with patch("github_jira_sync_app.main.JIRA") as MockJIRA:
        client = MagicMock()
        MockJIRA.return_value = client

        # Default: no existing issues
        client.enhanced_search_issues.return_value = []

        # create_issue returns a mock with permalink
        new_issue = MagicMock()
        new_issue.permalink.return_value = "https://my-jira.atlassian.net/browse/TEST-1"
        new_issue.key = "TEST-1"
        client.create_issue.return_value = new_issue

        ctx = MagicMock()
        ctx.client = client
        ctx.new_issue = new_issue

        def set_existing_issues(issues=None):
            if issues is None:
                existing = MagicMock()
                existing.key = "TEST-99"
                existing.fields.components = []
                issues = [existing]
            client.enhanced_search_issues.return_value = issues
            ctx.existing_issue = issues[0] if issues else None

        ctx.set_existing_issues = set_existing_issues

        yield ctx
