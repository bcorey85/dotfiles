---
description: Move the current Jira ticket to a new status (e.g., /move-ticket in review)
allowed-tools: [Bash, Read, mcp__jira__getTransitionsForJiraIssue, mcp__jira__transitionJiraIssue]
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

3. **Fetch available transitions** using `getTransitionsForJiraIssue` with the Jira Cloud ID from `JIRA.md` and the ticket key.

4. **Match the user's input** against the available transition names. Use case-insensitive fuzzy matching (e.g., "review" matches "In Review", "Peer Review", "Ready for Review", etc.). If no match or ambiguous, show the available transitions and ask the user to pick.

5. **Execute the transition** using `transitionJiraIssue`. IMPORTANT — the `transition` parameter is an **object**, not a string:
   ```
   cloudId: <from `JIRA.md`>
   issueIdOrKey: <ticket key>
   transition: {"id": "<matched transition id>"}
   ```

   Common mistakes to avoid:
   - WRONG: `transitionId: "31"` — that param belongs to a different tool
   - WRONG: `transition: "31"` — must be an object, not a string
   - RIGHT: `transition: {"id": "31"}`

6. **Confirm** to the user: "Moved <TICKET> to **<status name>**."

## Arguments

$ARGUMENTS
