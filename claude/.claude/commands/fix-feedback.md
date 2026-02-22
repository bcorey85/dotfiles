---
description: Dispatch parallel frontend and backend coder subagents to fix valid code review feedback
allowed-tools: [Task, Read, Glob, Grep]
---

# Fix Code Review Feedback

Dispatch parallel frontend-coder and backend-coder subagents to investigate and resolve valid issues from the most recent code review.

## Modifiers

- `+fast` — Use Haiku model for coder subagents. Use when review findings are trivial (typos, simple style fixes).
- `+deep` — Use Opus model for coder subagents. Use for complex review findings that require deeper reasoning to fix correctly.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt.

2. **Parse the review feedback** from the conversation to categorize issues as frontend or backend

3. **Launch coder agents in parallel** using a single message with multiple Task tool calls:

   **Frontend Coder** (`subagent_type: frontend-coder`):
   - Pass all frontend-specific issues with file paths and line numbers
   - Instruct the agent to investigate and fix each valid issue
   - Include enough context from the review for the coder to understand the problem

   **Backend Coder** (`subagent_type: backend-coder`):
   - Pass all backend-specific issues with file paths and line numbers
   - Instruct the agent to investigate and fix each valid issue
   - Include enough context from the review for the coder to understand the problem

   If all issues are frontend-only or backend-only, launch only the relevant coder agent.

4. **After coders complete**, summarize:
   - Which issues were fixed
   - Any issues intentionally skipped (with reasoning)
   - Any new concerns discovered
   - If any issue requires architectural rethinking, recommend the user run `/eng-plan` instead

## Validation

Each agent should verify issues are valid before fixing. Skip issues that are:
- False positives or stylistic preferences
- Out of scope for a quick fix
- Blocked by other unresolved issues
- Architectural in nature (recommend `/eng-plan` instead)
