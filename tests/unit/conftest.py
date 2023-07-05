from unittest.mock import patch

import pytest


@pytest.fixture(scope="session")
def signature_mock(request):
    """Set up webdriver fixture."""

    with patch("github_jira_sync_app.main.verify_signature", wraps=lambda *x: None) as signature:
        yield signature
        signature.assert_called()
