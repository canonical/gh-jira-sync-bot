import logging
import os

import requests
import yaml
from dotenv import load_dotenv
from fastapi import Body
from fastapi import FastAPI
from github import Github
from github import GithubException
from github import GithubIntegration
from yaml.scanner import ScannerError

load_dotenv()

with open("settings.yaml") as file:
    DEFAULT_SETTINGS = yaml.safe_load(file)


def define_logger():
    """Define logger to output to the file and to STDOUT."""
    log = logging.getLogger("api-demo-server")
    log.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        fmt="%(asctime)s (%(levelname)s) %(message)s", datefmt="%d.%m.%Y %H:%M:%S"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    log.addHandler(stream_handler)

    log_file = os.environ.get("DEMO_SERVER_LOGFILE", "demo_server.log")
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


@app.post("/")
def bot(payload: dict = Body(...)):

    # Check if the event is a GitHub PR creation event
    if not all(k in payload.keys() for k in ["action", "issue"]) and payload["action"] == "opened":
        return "ok"

    if payload["sender"]["login"] == "syncronize-issues-to-jira[bot]":
        return "ok"

    owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]

    # Get a git connection as our bot
    # Here is where we are getting the permission to talk as our bot and not
    # as a Python webservice
    git_connection = Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_repo_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")
    try:
        settings_content = repo.get_contents(
            ".github/workflows/.jira_sync_config55.yaml"
        ).decoded_content
    except GithubException:
        logger.info("Settings file was not found, use default")
        settings_content = b""

    try:
        settings = yaml.safe_load(settings_content)
    except ScannerError:
        logger.warning("YAML file is invalid, use default")
        settings = {}

    merge_dicts(settings, DEFAULT_SETTINGS)

    settings = settings["settings"]

    if not settings["add_comment"]:
        return "ok"

    issue = repo.get_issue(number=payload["issue"]["number"])

    response = requests.get(url="https://picsum.photos/200/300")
    meme_url = response.url

    issue.create_comment(f"![Alt Text]({meme_url})")
    return "ok"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
