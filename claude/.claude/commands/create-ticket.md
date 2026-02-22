---
description: PM command — pull a Notion spec and create Jira ticket(s) from its acceptance criteria
allowed-tools: [Bash, Read, Glob, Grep, mcp__notion__notion-search, mcp__notion__notion-fetch, mcp__notion__notion-update-page, mcp__jira__createJiraIssue, mcp__jira__getJiraIssue, mcp__jira__searchJiraIssuesUsingJql]
---

# Create Jira Tickets from Notion Spec

Read a Notion spec and create Jira tickets from its acceptance criteria. This is a PM-side command.

## Instructions

### Step 1: Find the Notion Spec

The user may provide:
- **A spec name** ("repo standup") — search Notion for it
- **A Notion page ID or URL** — fetch directly
- **Nothing** — search the Specs DB for specs in "Ready" status that don't have a Jira Key yet

Use `notion-search` to find the spec, then `notion-fetch` to read the full content.

### Step 2: Extract Acceptance Criteria

Parse the spec content to find the **Acceptance Criteria** section. Each criterion becomes a Jira ticket.

Present the extracted criteria to the user and confirm before creating tickets.

### Step 3: Create Jira Tickets

For each acceptance criterion:
- Create a Jira Task via `createJiraIssue` in project `TAS` (cloud ID: `ce38e0b7-717f-44a8-9ff0-aeac82a26560`)
- **Summary**: concise version of the criterion
- **Description**: include the full criterion text + a link back to the Notion spec URL
- If there are many criteria, ask the user if they want:
  - One ticket per criterion
  - Grouped tickets (related criteria merged)
  - A single parent ticket with subtasks

### Step 4: Update the Notion Spec

After creating tickets:
- Update the spec's `Jira Key` property with the primary ticket key
- Update the **Jira Tickets** section in the spec content with links to all created tickets
- Update spec **Status** from "Draft" to "Ready" (if still Draft)

### Step 5: Summary

Present:
- Link to the Notion spec
- List of Jira tickets created (keys + summaries)
- Suggested next step: "Dev can now `git checkout -b JIRAPROJECT-TICKETNUMBER-description` and run `/pull-ticket`"

### Step 6: Log MCP Usage

Log each Notion and Jira tool call to `docs/mcp-usage.jsonl`.

## Arguments

$ARGUMENTS
