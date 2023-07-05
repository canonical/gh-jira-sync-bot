import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(Path(__file__).parent / "dumm_env", verbose=True)
assert os.environ["JIRA_INSTANCE"]

# import only after we set dummy environment
from github_jira_sync_app.main import app  # noqa: E402

client = TestClient(app)


def _get_json(file_name):
    with open(Path(__file__).parent / "payloads" / file_name) as file:
        return json.load(file)


def test_comment_created_by_bot():
    data_hash = "sha256=38be3341f7b03bb234534be165ce4444d52bd95e798f547cabb1622db3628caa"
    response = client.post(
        "/",
        json=_get_json("comment_created.json"),
        headers={"x-hub-signature-256": data_hash},
    )

    assert response.status_code == 200
    assert response.json() == {"msg": "Action was triggered by bot. Ignoring."}
