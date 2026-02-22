---
description: Smart refactorer — analyzes the code and dispatches the right coder subagent(s)
allowed-tools: [Task, Read, Glob, Grep]
---

# Refactor

Analyze the code to refactor, determine whether it's frontend, backend, or fullstack, and dispatch the appropriate coder subagent(s).

## Modifiers

- `+fast` — Use Haiku model for coder subagents. Use for simple renames, extract-variable, or mechanical refactors.
- `+deep` — Use Opus model for coder subagents. Use for complex refactors involving multiple interacting systems, subtle architectural changes, or tricky migration of patterns.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Analyze the refactoring target** described below:
   - Read the referenced files to understand the current code
   - Determine if this is a **frontend** refactor (components, pages, stores, styles), a **backend** refactor (models, controllers/views, services, middleware, migrations), or **both**
   - Identify the refactoring goal: structure, readability, performance, maintainability, pattern alignment

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls

   For each coder:
   - Pass the refactoring description and any relevant context you gathered
   - Instruct it to: read and understand the existing code, implement the refactoring step by step, and ensure no functionality is broken
   - If the refactor turns out to need architectural redesign, have it report back and recommend `/eng-plan` instead

4. **After coder(s) complete**, summarize:
   - What was refactored and why
   - What changed structurally
   - Any related concerns or follow-up items

## Code to refactor

$ARGUMENTS
