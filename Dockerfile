from --platform=$BUILDPLATFORM ubuntu:22.04
LABEL org.opencontainers.image.source=https://github.com/canonical/gh-jira-sync-bot

COPY ./pyproject.toml .
COPY ./github_jira_sync_app ./github_jira_sync_app

RUN apt-get update && \
    apt-get install -y python3.10 python3-pip && \
    python3.10 -m pip install . && \
    apt remove -y python3-pip && \
    apt autoremove -y

EXPOSE 3000
ENTRYPOINT ["uvicorn", "github_jira_sync_app.main:app", "--host=0.0.0.0", "--port=3000"]
