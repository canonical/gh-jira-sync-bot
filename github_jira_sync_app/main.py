import hashlib
import hmac
import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from fastapi import Body
from fastapi import FastAPI
from fastapi import HTTPException
from github import Github
from github import GithubException
from github import GithubIntegration
from jira import JIRA
from mistletoe import Document  # type: ignore[import]
from mistletoe.contrib.jira_renderer import JIRARenderer  # type: ignore[import]
from starlette.requests import Request
from starlette.responses import Response
from yaml.scanner import ScannerError

jira_text_renderer = JIRARenderer()

load_dotenv()

jira_instance_url = os.getenv("JIRA_INSTANCE", "")
jira_username = os.getenv("JIRA_USERNAME", "")
jira_token = os.getenv("JIRA_TOKEN", "")

assert jira_instance_url, "URL to your Jira instance must be provided via JIRA_INSTANCE env var"
assert jira_username, "Jira username must be provided via JIRA_USERNAME env var"
assert jira_token, "Jira API token must be provided via JIRA_TOKEN env var"

jira_issue_description_template = """
This issue was created from GitHub Issue {gh_issue_url}
Issue was submitted by: {gh_issue_author}

PLEASE KEEP ALL THE CONVERSATION ON GITHUB

{gh_issue_body}
"""

gh_comment_body_template = """
Thank you for reporting your feedback to us!

The internal ticket has been created: {jira_issue_link}.

> This message was autogenerated
"""


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


with open(Path(__file__).parent / "settings.yaml") as file:
    _file_settings = yaml.safe_load(file)

_env_settings = yaml.safe_load(os.getenv("DEFAULT_BOT_CONFIG", "{}"))

DEFAULT_SETTINGS = _env_settings or _file_settings

app_id = os.getenv("APP_ID", "")
app_key = os.getenv("PRIVATE_KEY", "")
app_key = app_key.replace("\\n", "\n")  # since docker env variables do not support multiline

git_integration = GithubIntegration(
    app_id,
    app_key,
)


app = FastAPI()


@app.middleware("http")
async def catch_exceptions_middleware(request, call_next):
    """Middleware to catch all exceptions.

    All exceptions that were raised during handling of the request will be caught
    and logged with the traceback, then 500 response will be returned to the user.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Exception occurred")
        return Response("Internal server error", status_code=500)


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

    if not all(k in payload.keys() for k in ["action", "issue"]):
        return {"msg": "Action wasn't triggered by Issue action. Ignoring."}

    if "pull_request" in payload["issue"]:
        return {"msg": "Action was triggered by PR comment. Ignoring."}

    if payload["sender"]["login"] == os.getenv("BOT_NAME"):
        return {"msg": "Action was triggered by bot. Ignoring."}

    if "comment" in payload.keys():
        # validate issue_comment webhooks
        if payload["action"] != "created" and "comment" in payload.keys():
            return {
                "msg": f"Action was triggered by Issue Comment '{payload['action']}'. Ignoring."
            }
    else:
        # validate issue webhooks
        if payload["action"] not in ["opened", "edited", "closed", "reopened", "labeled"]:
            return {"msg": f"Action was triggered by Issue {payload['action']}. Ignoring."}

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
        contents = repo.get_contents(".github/.jira_sync_config.yaml")
        settings_content = contents.decoded_content  # type: ignore[union-attr]
    except GithubException:
        msg = ".github/.jira_sync_config.yaml file was not found"
        logger.error(f"{repo_name}: {msg}")
        return {"msg": msg}

    try:
        settings = yaml.safe_load(settings_content)
    except ScannerError:
        msg = ".github/.jira_sync_config.yaml file is invalid. Check syntax."
        logger.error(f"{repo_name}: {msg}")
        return {"msg": msg}

    merge_dicts(settings, DEFAULT_SETTINGS)

    settings = settings["settings"]

    if not settings["jira_project_key"]:
        msg = "Jira project key is not specified. Add `jira_project_key` key to the settings file."
        logger.warning(f"{repo_name}: {msg}")
        return {"msg": msg}

    if not settings["status_mapping"]:
        msg = "Status mapping is not specified. Add `status_mapping` key to the settings file."
        logger.warning(f"{repo_name}: {msg}")
        return {"msg": msg}

    labels = settings["labels"] or []
    allowed_labels = [label.lower() for label in labels]
    payload_labels = [label["name"].lower() for label in payload["issue"]["labels"]]
    if allowed_labels and not any(label in allowed_labels for label in payload_labels):
        msg = "Issue is not labeled with the specified label"
        logger.warning(f"{repo_name}: {msg}")
        return {"msg": msg}

    jira = JIRA(jira_instance_url, basic_auth=(jira_username, jira_token))
    jira_task_desc_match = f"This issue was created from GitHub Issue {issue.html_url}"
    existing_issues = jira.search_issues(
        rf'project="{settings["jira_project_key"]}" AND '
        + rf'description ~"\"{jira_task_desc_match}\""',
        json_result=False,
    )
    assert isinstance(existing_issues, list), "Jira did not return a list of existing issues"
    issue_body = issue.body if settings["sync_description"] else ""
    if issue_body:
        doc = Document(issue_body)
        issue_body = jira_text_renderer.render(doc)

    issue_description = jira_issue_description_template.format(
        gh_issue_url=issue.html_url,
        gh_issue_author=issue.user.login,
        gh_issue_body=issue_body,
    )

    issue_type = "Bug"
    if settings["label_mapping"]:
        for label in payload_labels:
            if label in settings["label_mapping"]:
                issue_type = settings["label_mapping"][label]
                break

    issue_dict: dict[str, Any] = {
        "project": {"key": settings["jira_project_key"]},
        "summary": issue.title,
        "description": issue_description,
        "issuetype": {"name": issue_type},
    }
    if settings["epic_key"]:
        issue_dict["parent"] = {"key": settings["epic_key"]}

    if settings["components"]:
        allowed_components = [c.name for c in jira.project_components(settings["jira_project_key"])]

        issue_dict["components"] = [
            {"name": component}
            for component in settings["components"]
            if component in allowed_components
        ]

    opened_status = settings["status_mapping"]["opened"]
    closed_status = settings["status_mapping"]["closed"]
    not_planned_status = settings["status_mapping"].get("not_planned", closed_status)

    msg = ""
    if not existing_issues:
        if payload["action"] == "closed":
            return {"msg": "Issue in Jira doesn't exist and GitHub issue was closed. Ignoring."}

        new_issue = jira.create_issue(fields=issue_dict)
        existing_issues.append(new_issue)

        if settings["add_gh_comment"]:
            issue.create_comment(
                gh_comment_body_template.format(jira_issue_link=new_issue.permalink())
            )

        # need this since we allow to sync issue on many actions. And if someone commented
        # we first create a Jira issue, then create a comment
        msg = "Issue was created in Jira. "
    else:
        jira_issue = existing_issues[0]
        if payload["action"] == "closed":
            if payload["issue"]["state_reason"] == "not_planned":
                jira.transition_issue(jira_issue, not_planned_status)
                return {"msg": "Closed existing Jira Issue as not planned"}
            else:
                jira.transition_issue(jira_issue, closed_status)
                return {"msg": "Closed existing Jira Issue"}
        elif payload["action"] == "reopened":
            jira.transition_issue(jira_issue, opened_status)
            return {"msg": "Reopened existing Jira Issue"}
        elif payload["action"] == "edited":
            if settings["components"]:
                # need to append components to the existing list
                for component in jira_issue.fields.components:
                    issue_dict["components"].append({"name": component.name})

            jira_issue.update(fields=issue_dict)
            return {"msg": "Updated existing Jira Issue"}

    if settings["sync_comments"] and payload["action"] == "created" and "comment" in payload.keys():
        # new comment was added to the issue

        comment_body = payload["comment"]["body"]
        doc = Document(comment_body)
        comment_body = jira_text_renderer.render(doc)
        jira.add_comment(
            existing_issues[0],
            f"User *{payload['sender']['login']}* commented:\n {comment_body}",
        )
        return {"msg": msg + "New comment from GitHub was added to Jira"}

    if not msg:
        return {"msg": "No action performed"}
    else:
        return {"msg": msg}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
