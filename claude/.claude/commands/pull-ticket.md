---
description: Pull Jira ticket context for the current branch before coding (dev command)
allowed-tools: [Bash, Read, Glob, Grep, mcp__jira__getJiraIssue, mcp__jira__searchJiraIssuesUsingJql]
---

# Pull Ticket Context

Fetch the Jira ticket details for the current branch so you have full context before coding.

## Instructions

1. **Get the current branch name**:
   ```bash
   git branch --show-current
   ```

2. **Extract the Jira ticket number** from the branch name (format: `JIRAPROJECT-TICKETNUMBER-description`). If the branch doesn't contain a ticket number, ask the user which ticket to pull.

3. **Fetch the Jira ticket** using `getJiraIssue` with cloud ID `ce38e0b7-717f-44a8-9ff0-aeac82a26560`:
   - Summary, description, acceptance criteria
   - Current status
   - Any comments with context

4. **Check for subtasks** — if the ticket has subtasks, fetch them too using JQL:
   ```
   parent = JIRAPROJECT-TICKETNUMBER
   ```

5. **Check for a local product spec** — Glob for `/product-specs/*.md` files that reference the ticket key. If found, read it for additional context.

6. **Present a summary** to the user:
   - Jira ticket: key, summary, status, acceptance criteria
   - Subtasks and their statuses (if any)
   - Local spec reference (if found)
   - Suggested approach based on the context

7. **Log MCP usage** to `docs/mcp-usage.jsonl` for each tool call.

## Design Note

Devs pull context from Jira only — Notion is the PM's domain. The Jira ticket description should contain everything needed to implement (summary, AC, and a link to the Notion spec if more context is desired).

## Arguments

$ARGUMENTS
