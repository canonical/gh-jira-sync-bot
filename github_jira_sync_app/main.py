import os

import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from github import Github
from github import GithubIntegration

load_dotenv()


app_id = os.getenv("APP_ID")
app_key = os.getenv("PRIVATE_KEY")
git_integration = GithubIntegration(
    app_id,
    app_key,
)

app = FastAPI()


@app.post("/")
def bot(request):
    # Get the event payload
    payload = request.json

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
    settings = repo.get_contents(".github/workflows/.jira_sync_config.yaml")
    print(settings)

    issue = repo.get_issue(number=payload["issue"]["number"])

    # Call meme-api to get a random meme
    response = requests.get(url="https://picsum.photos/200/300")
    # if response.status_code != 200:
    #     return 'ok'

    # Get the best resolution meme
    meme_url = response.url
    # Create a comment with the random meme
    issue.create_comment(f"![Alt Text]({meme_url})")
    return "ok"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=3000)
