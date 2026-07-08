---
name: pull-ticket
description: Pull Jira ticket context for the current branch before coding. Use for "pull the ticket", "get the Jira context", "what does the ticket say" when a branch/ticket key is in play.
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__jira__getJiraIssue]
---

# Pull Ticket Context

Fetch the Jira ticket details for the current branch so you have full context before coding.

## Instructions

1. **Resolve the key and fetch the ticket** per `~/.claude/skills/_shared/jira-ticket.md` (read it). This skill is a **required-ticket caller**: no key in args or branch name → ask the user; Jira MCP unavailable → say so and stop.

2. **Check ticket status**:
   - If status is **"To Do"**: note in the summary that work is starting (transition it in Jira manually if your workflow requires).
   - If status is **"In Progress"**: no action needed, just note it in the summary.
   - If status is **"In Review"** or **"Done"**: warn the user — "This ticket is in [status]. Are you sure you want to work on it?"

3. **Present a summary** to the user:
   - Jira ticket: key, summary, status, acceptance criteria
   - Suggested approach based on the context

## Design Note

Devs pull context from Jira only — Notion is the PM's domain. The Jira ticket description should contain everything needed to implement (summary, AC, and a link to the Notion spec if more context is desired).

## Arguments

$ARGUMENTS
