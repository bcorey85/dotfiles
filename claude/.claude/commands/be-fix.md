---
description: Dispatch backend-coder directly to fix a bug or handle a small backend task
allowed-tools: [Task, Read, Glob, Grep]
---

# Backend Fix

Dispatch a backend-coder subagent directly to investigate and fix a backend bug or small task. No architect needed.

## Modifiers

- `+fast` — Use Haiku model. Use for trivial fixes like renames, typos, or simple one-line changes.
- `+deep` — Use Opus model. Use for complex bugs, race conditions, subtle logic errors, or anything requiring deeper reasoning.

## Instructions

1. **Check for modifiers**: If `+deep` is present, pass `model: "opus"` to the Task tool call below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to the coder.

2. **Launch a backend-coder agent** (`subagent_type: backend-coder`):
   - Pass the bug description / task below
   - Instruct it to:
     - Explore the relevant code to understand the current behavior
     - Identify the root cause
     - Implement the fix
     - Verify the fix doesn't break related functionality
   - If the issue turns out to be architectural (needs data model changes, new endpoints, etc.), have the agent report back and recommend the user run `/be-plan` instead

3. **After the coder completes**, summarize:
   - What the root cause was
   - What was changed and why
   - Any related concerns or follow-up items

## Task

$ARGUMENTS
