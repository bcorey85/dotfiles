---
description: Dispatch coder subagent(s) for implementation — auto-detects scope or accepts be/fe/fs modifier
allowed-tools: [Task, Read, Glob, Grep]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope
- `+fast` — Use Haiku model. For trivial tasks like renames, typos, or simple one-line changes.
- `+deep` — Use Opus model. For complex tasks requiring deeper reasoning.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Determine scope**:
   - If a scope modifier (`be`, `fe`, `fs`) was provided, use that
   - Otherwise, analyze the task description — read referenced files, check relevant directories — and determine if this is frontend, backend, or both

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls

   For each coder:
   - Pass the full task description and any relevant context
   - Instruct it to follow existing patterns in the codebase
   - Write tests if needed
   - Flag any ambiguities or issues
   - If the task turns out to be architectural, have it report back and recommend `/eng-plan` instead

4. **After coder(s) complete**, summarize:
   - What was implemented
   - Any issues flagged
   - Any follow-up items

For complex features requiring design decisions, use `/eng-plan` instead.

## Task

$ARGUMENTS
