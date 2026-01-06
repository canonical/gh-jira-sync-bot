To mitigate the bug causing duplicate issues (Ref: https://github.com/canonical/gh-jira-sync-bot/issues/57), 
we can introduce a condition to check if the `issue.opened` webhook includes a `labels` field in 
its payload. If the `labels` field is present, we can safely skip processing the `issue.opened` webhook, 
knowing that a subsequent `issue.labeled` webhook will arrive to handle the labeling.

Example payload [issue_created_with_label.json](tests/unit/payloads/issue_created_with_label.json)

This will change the architecture as per diagram, with main change highlighted in purple

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
    rect rgb(200, 150, 255)
    App2->>GH: Return 200 as we ignore issue opened with labels
    end %end 1st rectangle block
    end %end parallel block
    
    rect rgb(200, 150, 255)
    App1->>Jira: Searches for existing Jira issues
    Jira->>App1: Returns None, as there is no Jira issue
    App1->>Jira: Creates/updates Jira issue
    App1->>repo: (Optional) Adds a comment on the Issue
    App1->>GH: Returns web response
    end %end 2nd rectangle block
```