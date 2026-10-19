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
      
  # (Optional) GitHub labels. Issues and enabled orphaned PRs must match at least one.
  # If omitted or empty, no label restriction applies. PR tracking must still be enabled.
  labels:
    - bug
    - custom
      
  # (Optional) (Default: false) Add a new comment in GitHub with a link to Jira created issue
  add_gh_comment: false

  # (Optional) (Default: false) Add a 'synced-to-jira' label to newly created issues once a
  # corresponding ticket is successfully created in Jira.
  # This label serves as confirmation that the issue sync process was completed successfully.
  add_gh_synced_label: false

  # (Optional) (Default: false) Create Jira tickets for newly opened PRs without linked issues.
  # Subject to the label filter above.
  sync_orphaned_prs: false
  
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

  # (Optional) JIRA issue's summary
  # This field can be used to customize the JIRA issue's summary (title).
  # The value of the field will be passed to the python
  # format() method to generate the JIRA summary. The GH issue
  # variable will be captured in the format() method so that users can
  # use GH issue attribute's values to build the JIRA summary.
  # See GH issue definition :
  # https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28
  #
  # Examples:
  # to use fixed title "github issue": "github issue"
  # to use GH issue title: "{issue.title}"
  # to add prefix "[GitHub]" : "[GitHub] {issue.title}"
  # to add user in the title (between square brackets): "[{issue.user.login}] {issue.title}"
  summary: "{issue.title}"

  # (Optional) set to True if GitHub issue labels should be synced to Jira.
  # Note, that will override all the labels in Jira.
  sync_labels: false
```

### Orphaned Pull Requests

Set `settings.sync_orphaned_prs: true` in `.github/.jira_sync_config.yaml` to create a Jira
ticket when a pull request is opened without a linked GitHub issue. Omit the setting or set
it to `false` to ignore PRs (the default).

Linked issues are determined using GitHub's `closingIssuesReferences`, including issues
linked through the PR's Development section or recognized closing keywords such as
`Fixes #123`. Plain mentions of issues are not closing links. GitHub's rules for closing
links apply, including restrictions for PRs targeting non-default branches. If the lookup
fails, processing fails so the webhook can be retried rather than creating a speculative ticket.

Orphaned PRs must match at least one configured `settings.labels` value (case-insensitive).
PRs with no matching label, including unlabeled PRs, are ignored. If `settings.labels` is
omitted, null, or an empty list, no label restriction applies. PR tracking must still be
enabled with `settings.sync_orphaned_prs: true`. Labels are checked when the PR is opened;
adding a matching label later does not trigger ticket creation.

The ticket uses the existing project, summary, description, issue-type mapping, epic,
and component settings, and includes the PR
URL and author. Optional GitHub comments and synced labels also apply. Redelivered webhooks
reuse the existing Jira ticket. Only the `opened` event is handled: later PR edits, comments,
closing, merging, and links added after opening do not update or remove the ticket.

Enable the Pull requests webhook event and permissions described below before enabling
this setting.


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
     - Pull requests: read-only when orphaned PR tracking is enabled; read and write if
       `add_gh_comment` or `add_gh_synced_label` is also enabled
   - Subscribe to these events:  
     - Issues  
     - Issue comments  
     - Pull requests (when orphaned PR tracking is enabled)
