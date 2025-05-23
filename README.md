## About

Lightweight FastAPI server to serve GitHub bot that synchronizes issues from GitHub to Jira.

In order to use this bot, you need to create a GitHub App. GitHub App registers application that should receive webhooks on selected events.


## Client side configuration

In order to use this bot, you need to create `.github/.jira_sync_config.yaml` file in your repository.
The file should contain the following fields:
```yaml
settings:
    # Jira project key to create the issue in
  jira_project_key: "MTC"
  
  # Dictionary mapping GitHub issue status to Jira issue status
  status_mapping:
    opened: Untriaged
    closed: done
    # (Optional) Use different status for GitHub issues closed as not planned (instead of closed as
    # completed)
    # https://github.blog/changelog/2022-03-10-the-new-github-issues-march-10th-update/#%F0%9F%95%B5%F0%9F%8F%BD%E2%99%80%EF%B8%8F-issue-closed-reasons
    # If not specified, `closed` status will be used.
    not_planned: rejected
    
  # (Optional) Jira project components that should be attached to the created issue
  # Component names are case-sensitive
  components:
    - IoT
    - DACH TT
      
  # (Optional) GitHub labels. Only issues with one of those labels will be synchronized.
  # If not specified, all issues will be synchronized
  labels:
    - bug
    - custom
      
  # (Optional) (Default: false) Add a new comment in GitHub with a link to Jira created issue
  add_gh_comment: false

  # (Optional) (Default: false) Add a 'synced-to-jira' label to newly created issues once a
  # corresponding ticket is successfully created in Jira.
  # This label serves as confirmation that the issue sync process was completed successfully.
  add_gh_synced_label: false
  
  # (Optional) (Default: true) Synchronize issue description from GitHub to Jira
  sync_description: true
  
  # (Optional) (Default: true) Synchronize comments from GitHub to Jira
  sync_comments: true
  
  # (Optional) (Default: None) Parent Epic key to link the issue to
  epic_key: "MTC-296"
      
  # (Optional) Dictionary mapping GitHub issue labels to Jira issue types. 
  # If label on the issue is not in specified list, this issue will be created as a Bug
  label_mapping:
    enhancement: Story
```


## Server Configuration
You need this section only if you deploy your own bot. However, even for this purpose I recommend to use https://github.com/canonical/charmed-gh-jira-sync-bot

The following environment variables are required:  
`APP_ID` - GitHub App ID  
`PRIVATE_KEY` - GitHub App private key  
`WEBHOOK_SECRET` - GitHub App webhook secret  
`JIRA_INSTANCE` - Jira instance URL  
`JIRA_USERNAME` - Jira username  
`JIRA_TOKEN` - Jira API token  

## GitHub App installation
This app is meant to be installed as a GitHub application.  

1. [Register a new GitHub app](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app).  
2. Make sure to:  
   - Generate a private key for the app.  
   - Set up a webhook secret.  
   - Add these repository permissions:  
     - Issues: read and write  
     - Metadata: read-only  
     - Single file: read-only (Path: `.github/.jira_sync_config.yaml`)  
   - Subscribe to these events:  
     - Issues  
     - Issue comments  
