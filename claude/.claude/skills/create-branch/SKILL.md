---
name: create-branch
description: Create a feature branch (optionally off a sprint branch), push it, and open a draft PR to track changes
allowed-tools: [Bash, Read, Skill, mcp__jira__getJiraIssue]
---

# Create Branch

Create a feature branch, push it, and open a draft PR so the team can track changes from the start.

## Usage

```
/create-branch off <base-branch>
/create-branch <ticket-key> off <base-branch>
/create-branch <ticket-key>
/create-branch <branch-name>
```

Examples:
- `/create-branch off Sprint-A-2026` — base off sprint branch, infer ticket from context
- `/create-branch TAS-20 off Sprint-A-2026` — explicit ticket + sprint branch
- `/create-branch TAS-20` — base off main (default)
- `/create-branch my-experiment` — no ticket, custom branch name off main

## Instructions

### Step 1: Parse Arguments

Parse `$ARGUMENTS` to extract:
- **Base branch**: everything after `off `. If no `off` keyword, default to `main`.
- **Ticket key or branch name**: everything before `off ` (or the entire argument if no `off`). Could be a Jira key like `TAS-20`, a descriptive name, or empty.

### Step 2: Resolve Branch Name

- **If a Jira ticket key was provided** (matches pattern `[A-Z]+-\d+`): fetch the ticket using `getJiraIssue` (Cloud ID from `JIRA.md`) to get the summary. Build the branch name: `<TICKET-KEY>-<slugified-summary>` (lowercase, hyphens, max ~50 chars). Example: `TAS-20-dockerize-dev-environment`.
- **If a descriptive name was provided** (not a ticket key): use it directly as the branch name.
- **If nothing was provided**: ask the user — "What should the branch be named? (Jira ticket key like TAS-20, or a descriptive name)"

### Step 3: Create the Branch

```bash
git checkout <base-branch> && git pull && git checkout -b <branch-name>
```

If the base branch doesn't exist locally, try fetching it first:
```bash
git fetch origin <base-branch> && git checkout <base-branch> && git pull && git checkout -b <branch-name>
```

If the base branch doesn't exist at all, stop and tell the user.

### Step 4: Push and Draft PR

Push the branch and create a draft PR against the base by invoking `/pr` via the Skill tool:

```
skill: "pr"
args: "+draft --base <base-branch>"
```

This delegates all PR creation logic (title convention, body format) and ensures the base branch is stored on the PR for downstream skills (`/pr`, `/verify-changes`) to read later.

### Step 5: Summary

Report to the user:
- Branch created: `<branch-name>` off `<base-branch>`
- Draft PR URL (from `/pr` output)
- If a Jira ticket was used: remind them to `/pull-ticket` for full context before coding

## Arguments

$ARGUMENTS
