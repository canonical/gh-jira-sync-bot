import os
from importlib import reload
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient


@pytest.fixture()
def signature_mock(request, client):
    """Set up webdriver fixture."""
    with patch("github_jira_sync_app.main.verify_signature", wraps=lambda *x: None) as signature:
        yield signature
        signature.assert_called()


# Fixture that prepares the environment variables ad-hoc for each test
# The individual variables are passed using
# @pytest.mark.parametrize("client",[{"bot_configs":{"ENV_NAME": ENV_VALUE,...}}],indirect=True)
# and overwrite what is found in dumm_env
# The parametrization is optional, so tests that work with the defaults do not require any change
@pytest.fixture(
    scope="function",
    params=[
        {"bot_configs": None},
    ],
)
def client(request):
    # Take in optional configuration
    if request.param["bot_configs"] is None:
        bot_configs = {}
    else:
        bot_configs = request.param["bot_configs"]

    # Apply configuration (if present)
    for k, v in bot_configs.items():
        os.environ[k] = v
        assert k == "DEFAULT_BOT_CONFIG"

    assert os.environ["JIRA_INSTANCE"]

    # Reload application so that new environment variables take effect
    import github_jira_sync_app.main

    reload(github_jira_sync_app.main)

    from github_jira_sync_app.main import app

    yield TestClient(app=app)

    # Teardown: restore default configuration for tests
    load_dotenv(Path(__file__).parent / "dumm_env", verbose=True)
    reload(github_jira_sync_app.main)
