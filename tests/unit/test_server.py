import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from github_jira_sync_app.main import app

client = TestClient(app)

os.environ["WEBHOOK_SECRET"] = "lr16xaodb2r4iy6he00uhacw9c9i4yvhlstqv9jy"


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
