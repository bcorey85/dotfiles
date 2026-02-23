---
name: cache-jira-transitions
description: Pull Jira transitions from MCP and cache them in JIRA.md
allowed-tools: [Bash, Read, Edit, mcp__jira__getTransitionsForJiraIssue]
---

# Cache Jira Transitions

Fetch the available Jira board transitions from the MCP API and update the Board Transitions table in `JIRA.md`.

## Instructions

1. **Find a ticket to query transitions against.** The Jira API requires an issue key to list transitions. Use the current branch to extract a ticket key:
   ```bash
   git branch --show-current
   ```
   If no ticket key is found in the branch name, search for any recent ticket:
   - Try `TAS-1` as a fallback (it should always exist).

2. **Read `JIRA.md`** to get the Cloud ID and see the current Board Transitions table.

3. **Fetch transitions** using `getTransitionsForJiraIssue`:
   ```
   cloudId: <from JIRA.md>
   issueIdOrKey: <ticket key from step 1>
   ```

4. **Replace the Board Transitions table** in `JIRA.md` using the Edit tool. The new table should:
   - Keep the same markdown table format: `| Status | Transition ID |`
   - Include ALL transitions returned by the API
   - Sort by transition ID numerically
   - Replace the old table entirely (from the `## Board Transitions` header's table through the last table row, stopping before the next section)

5. **Confirm** to the user: show the old vs new transitions and note any changes.

## Arguments

$ARGUMENTS
