---
description: Smart bug fixer — auto-detects scope or accepts be/fe/fs modifier, dispatches coder subagent(s), then auto-runs peer review
allowed-tools: [Task, Read, Glob, Grep, Skill]
---

# Fix

Analyze a bug or issue, determine scope, and dispatch the appropriate coder subagent(s) to investigate and fix it.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope
- `+fast` — Use Haiku model. For trivial fixes like renames, typos, or simple one-line changes.
- `+deep` — Use Opus model. For complex bugs, race conditions, subtle logic errors, or anything requiring deeper reasoning.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Determine scope**:
   - If a scope modifier (`be`, `fe`, `fs`) was provided, use that
   - Otherwise, analyze the issue — read referenced files, error messages, stack traces — and determine if this is frontend, backend, or both

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls

   For each coder:
   - Pass the full bug description and any relevant context you gathered
   - Instruct it to explore the code, identify the root cause, and implement the fix
   - Verify the fix doesn't break related functionality
   - If the issue turns out to be architectural, have it report back and recommend `/eng-plan` instead

4. **After coder(s) complete**, summarize:
   - What the root cause was
   - What was changed and why
   - Any related concerns or follow-up items

5. **Auto-dispatch peer review**: After summarizing the fix, tell the user: "Auto-dispatching `/peer-review` to check the fix before committing." Then invoke the `/peer-review` skill using the Skill tool (`skill: "peer-review"`). If the user passed `+fast` or `+deep`, pass the same modifier to the peer review invocation (e.g., `skill: "peer-review", args: "+fast"`). This step runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

## Issue

$ARGUMENTS
