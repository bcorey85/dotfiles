---
name: move-ticket
description: Move the current Jira ticket to a new status (e.g., /move-ticket in review)
allowed-tools: [Bash, Read, Skill, mcp__jira__transitionJiraIssue]
---

# Move Ticket

Transition the current branch's Jira ticket to a new status.

## Usage

```
/move-ticket <status>
```

Examples: `/move-ticket in progress`, `/move-ticket in review`, `/move-ticket done`

## Instructions

1. **Get the ticket key** from the current branch:
   ```bash
   git branch --show-current
   ```
   Extract the Jira ticket key (e.g., `TAS-4` from `TAS-4-column-controller`). If no ticket key is found, ask the user.

2. **Determine the target status** from `$ARGUMENTS`. If no arguments provided, ask the user: "What status? (e.g., in progress, in review, done)"

3. **Resolve transition ID** — check `JIRA.md` first, cache-refresh second:
   a. Read the **Board Transitions** table in `JIRA.md`. Case-insensitive fuzzy match the user's input against the status names (e.g., "review" matches "In Review", "progress" matches "In Progress").
   b. If a match is found, use that transition ID directly — **skip any API calls**.
   c. If NO match is found in `JIRA.md` (e.g., the table is missing or the status name is unfamiliar), AND `JIRA.md` has a Cloud ID and project key, invoke `/cache-jira-transitions` via the Skill tool to refresh the cached transitions. Then re-read `JIRA.md` and match again. If still no match or ambiguous after the refresh, show the available transitions and ask the user to pick.

4. **Execute the transition** using `transitionJiraIssue`. IMPORTANT — the `transition` parameter is an **object**, not a string:
   ```
   cloudId: <from `JIRA.md`>
   issueIdOrKey: <ticket key>
   transition: {"id": "<matched transition id>"}
   ```

   Common mistakes to avoid:
   - WRONG: `transitionId: "31"` — that param belongs to a different tool
   - WRONG: `transition: "31"` — must be an object, not a string
   - RIGHT: `transition: {"id": "31"}`

5. **Confirm** to the user: "Moved <TICKET> to **<status name>**."

## Arguments

$ARGUMENTS
