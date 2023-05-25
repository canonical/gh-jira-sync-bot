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

The following environment variables are required:  
`APP_ID` - GitHub App ID  
`PRIVATE_KEY` - GitHub App private key  
`WEBHOOK_SECRET` - GitHub App webhook secret  
`GITHUB_CLIENT_ID` - GitHub OAuth App client ID  
`GITHUB_CLIENT_SECRET` - GitHub OAuth App client secret  
`JIRA_INSTANCE` - Jira instance URL  
`JIRA_USERNAME` - Jira username  
`JIRA_TOKEN` - Jira API token  
