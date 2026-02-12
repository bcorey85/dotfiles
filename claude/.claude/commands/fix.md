---
description: Smart bug fixer — analyzes the issue and dispatches the right coder subagent(s)
allowed-tools: [Task, Read, Glob, Grep]
---

# Fix

Analyze the bug or issue, determine whether it's frontend, backend, or fullstack, and dispatch the appropriate coder subagent(s).

## Modifiers

- `+fast` — Use Haiku model for coder subagents. Use for trivial fixes like renames, typos, or simple one-line changes.
- `+deep` — Use Opus model for coder subagents. Use for complex bugs, race conditions, subtle logic errors, or anything requiring deeper reasoning.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Analyze the issue** described below:
   - Read any referenced files, error messages, or stack traces
   - Determine if this is a **frontend** issue (components, pages, stores, styles, composables), a **backend** issue (models, views, serializers, tasks, migrations), or **both**

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls

   For each coder:
   - Pass the full bug description and any relevant context you gathered
   - Instruct it to explore the code, identify the root cause, and implement the fix
   - If the issue turns out to be architectural, have it report back and recommend `/fe-plan`, `/be-plan`, or `/fs-plan` instead

4. **After coder(s) complete**, summarize:
   - What the root cause was
   - What was changed and why
   - Any related concerns or follow-up items

## Issue

$ARGUMENTS
