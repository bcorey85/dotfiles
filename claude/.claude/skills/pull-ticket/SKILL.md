---
name: pull-ticket
description: Pull Jira ticket context for the current branch before coding (dev command)
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__jira__getJiraIssue]
---

# Pull Ticket Context

Fetch the Jira ticket details for the current branch so you have full context before coding.

## Instructions

1. **Get the current branch name**:

   ```bash
   git branch --show-current
   ```

2. **Extract the Jira ticket number** from the branch name (format: `JIRAPROJECT-TICKETNUMBER-description`). If the branch doesn't contain a ticket number, ask the user which ticket to pull.

3. **Fetch the Jira ticket** using `getJiraIssue`. Resolve the Cloud ID portably: pass the Jira site hostname (e.g. `<site>.atlassian.net`) as `cloudId` if it's known from context (a ticket URL, project docs); otherwise call `getAccessibleAtlassianResources` first. If the Jira MCP tools aren't available in this session, say so and stop — don't guess ticket content. Pull:
   - Summary, description, acceptance criteria
   - Current status
   - Any comments with context

4. **Check ticket status**:
   - If status is **"To Do"**: note in the summary that work is starting (transition it in Jira manually if your workflow requires).
   - If status is **"In Progress"**: no action needed, just note it in the summary.
   - If status is **"In Review"** or **"Done"**: warn the user — "This ticket is in [status]. Are you sure you want to work on it?"

5. **Present a summary** to the user:
   - Jira ticket: key, summary, status, acceptance criteria
   - Suggested approach based on the context

## Design Note

Devs pull context from Jira only — Notion is the PM's domain. The Jira ticket description should contain everything needed to implement (summary, AC, and a link to the Notion spec if more context is desired).

## Arguments

$ARGUMENTS
