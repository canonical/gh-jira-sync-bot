# ASGI entrypoint for the fastapi-framework rock extension, which looks for a
# variable named `app` in app.py at the project root.
from github_jira_sync_app.main import app

__all__ = ["app"]
