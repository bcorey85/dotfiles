---
name: pull-ticket
description: Pull Jira ticket context for the current branch before coding (dev command)
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__jira__getJiraIssue, mcp__jira__searchJiraIssuesUsingJql]
---

# Pull Ticket Context

Fetch the Jira ticket details for the current branch so you have full context before coding.

## Instructions

1. **Get the current branch name**:
   ```bash
   git branch --show-current
   ```

2. **Extract the Jira ticket number** from the branch name (format: `JIRAPROJECT-TICKETNUMBER-description`). If the branch doesn't contain a ticket number, ask the user which ticket to pull.

3. **Fetch the Jira ticket** using `getJiraIssue` with the Jira Cloud ID from `JIRA.md`:
   - Summary, description, acceptance criteria
   - Current status
   - Any comments with context

4. **Check ticket status and auto-transition**:
   - If status is **"To Do"**: automatically move to "In Progress" by invoking the `/move-ticket in progress` skill via the Skill tool. Pulling a ticket implies starting work — no confirmation needed. Do NOT inline the Jira transition logic — always delegate to the `/move-ticket` skill.
   - If status is **"In Progress"**: no action needed, just note it in the summary.
   - If status is **"In Review"** or **"Done"**: warn the user — "This ticket is in [status]. Are you sure you want to work on it?"

5. **Check for subtasks** — if the ticket has subtasks, fetch them too using JQL:
   ```
   parent = JIRAPROJECT-TICKETNUMBER
   ```

6. **Present a summary** to the user:
   - Jira ticket: key, summary, status (including any transition made), acceptance criteria
   - Subtasks and their statuses (if any)
   - Suggested approach based on the context

## Design Note

Devs pull context from Jira only — Notion is the PM's domain. The Jira ticket description should contain everything needed to implement (summary, AC, and a link to the Notion spec if more context is desired).

## Arguments

$ARGUMENTS
