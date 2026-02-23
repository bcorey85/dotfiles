---
description: Dispatch coder subagent(s) for implementation, then auto-run peer review — auto-detects scope or accepts be/fe/fs modifier
allowed-tools: [Task, Read, Glob, Grep, Skill]
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

5. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching `/peer-review` to check the implementation before committing." Then invoke the `/peer-review` skill using the Skill tool (`skill: "peer-review"`). If the user passed `+fast` or `+deep`, pass the same modifier to the peer review invocation (e.g., `skill: "peer-review", args: "+fast"`). This step runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

For complex features requiring design decisions, use `/eng-plan` instead.

## Task

$ARGUMENTS
