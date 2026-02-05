---
description: Dispatch parallel frontend and backend architect subagents to investigate and resolve valid code review feedback
allowed-tools: [Task, Read, Glob, Grep]
---

# Fix Code Review Feedback

Dispatch parallel frontend-architect and backend-architect subagents to investigate and resolve valid issues from the most recent code review.

## Instructions

1. **Parse the review feedback** from the conversation to categorize issues as frontend or backend

2. **Launch both agents in parallel** using a single message with multiple Task tool calls:

   **Frontend Architect** (`subagent_type: frontend-architect`):
   - Pass all frontend-specific issues with file paths and line numbers
   - Instruct the agent to investigate and fix each valid issue

   **Backend Architect** (`subagent_type: backend-architect`):
   - Pass all backend-specific issues with file paths and line numbers
   - Instruct the agent to investigate and fix each valid issue

3. **After both complete**, summarize:
   - Which issues were fixed
   - Any issues intentionally skipped (with reasoning)
   - Any new concerns discovered

## Validation

Each agent should verify issues are valid before fixing. Skip issues that are:
- False positives or stylistic preferences
- Out of scope for a quick fix
- Blocked by other unresolved issues
