# General workflow

```mermaid
sequenceDiagram
    actor User
    participant repo as GitHub Repo
    participant GH as GitHub Backend
    participant App as Application
    User->>repo: Creates/modifies <br>issue or comments
    repo->>GH: Notifies backend
    GH->>App: Sends Webhook
    App->>App: Validates the webhook hash
    App->>App: Validates webhook's trigger
    App->>repo: Reads ".github/.jira_sync_config.yaml" file
    App->>Jira: Searches for existing Jira issues
    Jira->>App: Provides list of existing issues if any
    App->>Jira: Creates/updates Jira issue
    App->>repo: (Optional) Adds a comment on the Issue
    App->>GH: Returns web response

```

# Issue created from template (with labels)

This diagram illustrates a corner case scenario when issue is created from GitHub issue template that contains Labels.
In this case GitHub sends two webhooks in parallel that causes issues in the asynchronous (stateless) service.

```mermaid
sequenceDiagram
    actor User
    participant repo as GitHub Repo
    participant GH as GitHub Backend
    participant App1 as Application (Unit 1)
    participant App2 as Application (Unit 2)
    User->>repo: Creates an issue with a label <br>applied directly from the template
    repo->>GH: Notifies backend
    par
    GH->>App1: Sends Webhook (issue labeled)
    GH->>App2: Sends Webhook (issue opened)
    end

    par
    App1->>App1: Validates the webhook hash
    App1->>App1: Validates webhook's trigger
    App2->>App2: Validates the webhook hash
    App2->>App2: Validates webhook's trigger
    App1->>repo: Reads ".github/.jira_sync_config.yaml" file
    App2->>repo: Reads ".github/.jira_sync_config.yaml" file
    end
    
    par
    App1->>Jira: Searches for existing Jira issues
    App2->>Jira: Searches for existing Jira issues
    end

    par
    Jira->>App1: Returns None, as there is no Jira issue
    Jira->>App2: Returns None, as there is no Jira issue
    end
    
    par
    App1->>Jira: Creates/updates Jira issue
    App2->>Jira: Creates/updates Jira issue
    end

    par
    App1->>repo: (Optional) Adds a comment on the Issue
    App2->>repo: (Optional) Adds a comment on the Issue
    end
    
    par
    App1->>GH: Returns web response
    App2->>GH: Returns web response
    end

```