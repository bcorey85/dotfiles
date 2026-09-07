---
name: pull-ticket
description: Pull Jira ticket context for the current branch before coding. Use for "pull the ticket", "get the Jira context", "what does the ticket say" when a branch/ticket key is in play.
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__jira__getJiraIssue]
---

# Pull Ticket Context

Fetch the Jira ticket for the current branch before coding.

## Instructions

1. **Resolve plus fetch** per `~/.claude/skills/_shared/jira-ticket.md` (read it) — **required-ticket caller**: no key means ask; no MCP means stop.

2. **Check ticket status**:
   - 'To Do' means note work starting; 'In Progress' means note only; 'In Review' or 'Done' means warn and confirm.

3. **Present**: key, summary, status, acceptance criteria plus suggested approach.

## Design Note

Devs pull from Jira only (Notion is the PM domain). Ticket descriptions carry summary, AC, and a Notion link when needed.

## Arguments

$ARGUMENTS
