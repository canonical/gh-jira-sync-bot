import hashlib
import hmac
import logging
import os

import requests
import yaml
from dotenv import load_dotenv
from fastapi import Body
from fastapi import FastAPI
from fastapi import HTTPException
from github import Github
from github import GithubException
from github import GithubIntegration
from starlette.requests import Request
from yaml.scanner import ScannerError

load_dotenv()

with open("settings.yaml") as file:
    DEFAULT_SETTINGS = yaml.safe_load(file)


def define_logger():
    """Define logger to output to the file and to STDOUT."""
    log = logging.getLogger("sync-bot-server")
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s (%(levelname)s) %(message)s", datefmt="%d.%m.%Y %H:%M:%S"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    log_file = os.environ.get("SYNC_BOT_LOGFILE", "sync_bot.log")
    file_handler = logging.FileHandler(filename=log_file)
    file_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    return log


logger = define_logger()


app_id = os.getenv("APP_ID")
app_key = os.getenv("PRIVATE_KEY")
git_integration = GithubIntegration(
    app_id,
    app_key,
)

app = FastAPI()


def merge_dicts(d1, d2):
    """Merge the two dictionaries (d2 into d1) recursively.

    If the key from d2 exists in d1, then skip (do not override).

    Mutates d1
    """
    for key in d2:
        if key in d1 and isinstance(d1[key], dict) and isinstance(d2[key], dict):
            merge_dicts(d1[key], d2[key])
        elif key not in d1:
            d1[key] = d2[key]


def verify_signature(payload_body, secret_token, signature_header):
    """Verify that the payload was sent from GitHub by validating SHA256.

    Raise and return 403 if not authorized.

    Args:
        payload_body: original request body to verify (request.body())
        secret_token: GitHub app webhook token (WEBHOOK_SECRET)
        signature_header: header received from GitHub (x-hub-signature-256)

    """
    if not signature_header:
        raise HTTPException(status_code=403, detail="x-hub-signature-256 header is missing!")

    hash_object = hmac.new(secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=403, detail="Request signatures didn't match!")


@app.post("/")
async def bot(request: Request, payload: dict = Body(...)):
    body_ = await request.body()
    signature_ = request.headers.get("x-hub-signature-256")

    verify_signature(body_, os.getenv("WEBHOOK_SECRET"), signature_)

    # Check if the event is a GitHub PR creation event
    if not all(k in payload.keys() for k in ["action", "issue"]) and payload["action"] == "opened":
        return "ok"

    if payload["sender"]["login"] == "syncronize-issues-to-jira[bot]":
        return "ok"

    owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    git_connection = Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_repo_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")
    issue = repo.get_issue(number=payload["issue"]["number"])
    try:
        settings_content = repo.get_contents(".github/.jira_sync_config.yaml").decoded_content
    except GithubException:
        logger.error("Settings file was not found")
        issue.create_comment(".github/.jira_sync_config.yaml file was not found")
        return "ok"

    try:
        settings = yaml.safe_load(settings_content)
    except ScannerError:
        logger.error("YAML file is invalid")
        issue.create_comment(".github/.jira_sync_config.yaml file is invalid. Check syntax.")
        return "ok"

    merge_dicts(settings, DEFAULT_SETTINGS)

    settings = settings["settings"]

    if not settings["jira_instance"]:
        issue.create_comment(
            "Jira instance is not specified. Add jira_instance key to the settings file."
        )
        return "ok"

    if not settings["jira_project_key"]:
        issue.create_comment(
            "Jira project key is not specified. Add jira_project_key key to the settings file."
        )
        return "ok"

    if not settings["add_comment"]:
        return "ok"

    response = requests.get(url="https://picsum.photos/200/300")
    meme_url = response.url

    issue.create_comment(f"![Alt Text]({meme_url})")
    return "ok"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
