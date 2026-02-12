---
description: Dispatch parallel frontend and backend coders to fix a fullstack bug or small task
allowed-tools: [Task, Read, Glob, Grep]
---

# Fullstack Fix

Dispatch frontend-coder and backend-coder subagents in parallel to investigate and fix a fullstack bug or small task. No architects needed.

## Modifiers

- `+fast` — Use Haiku model for both coder subagents. Use for trivial fixes like renames, typos, or simple one-line changes.
- `+deep` — Use Opus model for both coder subagents. Use for complex bugs, race conditions, subtle logic errors, or anything requiring deeper reasoning.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to both Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Analyze the bug description** to determine what each side needs to investigate

3. **Launch both coder agents in parallel** using a single message with multiple Task tool calls:

   **Backend Coder** (`subagent_type: backend-coder`):
   - Pass the bug description with emphasis on backend-relevant aspects
   - Instruct it to explore the relevant code, identify root cause, and fix
   - If the issue is purely frontend, have it report back with findings

   **Frontend Coder** (`subagent_type: frontend-coder`):
   - Pass the bug description with emphasis on frontend-relevant aspects
   - Instruct it to explore the relevant code, identify root cause, and fix
   - If the issue is purely backend, have it report back with findings

4. **After both coders complete**, summarize:
   - What each coder found and fixed
   - Whether the root cause was frontend, backend, or both
   - Any integration concerns between the fixes
   - If the issue turns out to be architectural, recommend `/fs-plan` instead

## Task

$ARGUMENTS
