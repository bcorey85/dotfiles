---
name: add-ticket-description
description: Update a Jira ticket's description from a local file or user-provided content
allowed-tools: [Read, Glob, Grep, mcp__jira__getJiraIssue, mcp__jira__editJiraIssue]
---

# Add Ticket Description

Read content from a local file (or user-provided text) and update a Jira ticket's description with a high-level summary.

## Instructions

### Step 1: Identify the Ticket

The user may provide:
- **A Jira key** (e.g., `CHR-6`) — use directly
- **A URL** (e.g., `https://centerbase1.atlassian.net/browse/CHR-6`) — extract the key
- **Nothing** — infer from the current git branch name (e.g., `chr-6-migrate-to-monorepo` → `CHR-6`)

Read `mcp-references/JIRA.md` for the Cloud ID. Fetch the current ticket with `getJiraIssue` to see existing description and summary.

### Step 2: Gather Content

The user may provide:
- **A file path** — read the file and summarize it
- **Inline text** — use directly
- **Nothing** — ask what content to add

### Step 3: Draft the Description

Summarize the content into high-level bullet points suitable for a Jira ticket. Structure with markdown headings and bullet lists. Keep it concise — link to the source file for full details rather than duplicating everything.

Present the draft to the user and confirm before updating.

### Step 4: Update the Ticket

Use `editJiraIssue` to set the `description` field.

**CRITICAL — Jira MCP description format:**
- Pass `description` as a **plain markdown string** — the Jira MCP tool handles ADF conversion internally.
- Do **NOT** pass Atlassian Document Format (ADF) JSON objects. The tool will reject them.
- Markdown features that work: headings (`###`), bullet lists (`-`), bold (`**bold**`), inline code (`` `code` ``), links (`[text](url)`).

Example payload:
```json
{
  "description": "Summary paragraph.\n\n### Section\n\n- **Bold label:** detail\n- Another point\n- `inline code` works too"
}
```

### Step 5: Confirm

Report the updated ticket key and link.

## Arguments

$ARGUMENTS
