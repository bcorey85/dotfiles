---
name: move-ticket
description: Transition the Jira ticket for the current branch to a new status (e.g. "in progress", "in review"). Invoked by /pull-ticket and /pr; also user-invocable.
allowed-tools:
  [
    Bash,
    Read,
    Skill,
    mcp__jira__getJiraIssue,
    mcp__jira__getTransitionsForJiraIssue,
    mcp__jira__transitionJiraIssue,
    mcp__jira__getAccessibleAtlassianResources,
  ]
---

# Move Ticket

Transition a Jira ticket to the status named in the arguments (e.g. `/move-ticket in review`, `/move-ticket in progress`).

## Instructions

Execute in one pass — no approval pauses.

1. **Resolve the ticket key**: Use the key passed in arguments if present. Otherwise extract it from the branch name (`git branch --show-current`, format `JIRAPROJECT-TICKETNUMBER-description`). If neither yields a key, ask the user.

2. **Resolve the Cloud ID**: Read it from `docs/mcp-references/JIRA.md` if that file exists in the project; otherwise call `getAccessibleAtlassianResources` and use the single result (ask the user if there are several).

3. **Find the matching transition**: Call `getTransitionsForJiraIssue` for the ticket. Match the requested status against the available transitions case-insensitively (e.g. "in review" matches "In Review"). If no transition matches, report the available transitions and stop — do NOT guess a different one.

4. **Transition**: Call `transitionJiraIssue` with the matched transition ID.

5. **Report**: One line — ticket key, old status → new status. If the ticket is already in the requested status, report that and stop without erroring.

## Arguments

$ARGUMENTS
