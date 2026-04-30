---
name: code
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
   - If the task turns out to be architectural, have it report back and recommend `/eng-spec` instead

4. **After coder(s) complete**, summarize for the user AND build a handoff block for downstream review.

   User summary:
   - What was implemented
   - Any issues flagged
   - Any follow-up items

   Handoff block (passed as args to `/peer-review` in step 5). Schema is defined in `peer-review/SKILL.md` under "Handoff Block". Required fields:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what changed and why>
     tests-run: <command(s) and pass/fail status, or "none">
     flagged: <issues the coder explicitly flagged, or "none">
     iter: 1
   ```

   The handoff lets the reviewer skip rediscovery — file scope, change intent, and test status are upstream context the reviewer no longer has to reconstruct via `git diff` and full re-reads. Coders already know all of this; pass it forward instead of forcing re-discovery.

5. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching `/peer-review` to check the implementation before committing." Then invoke the `/peer-review` skill via the Skill tool with `skill: "peer-review"` and `args` containing the handoff block from step 4 plus any `+fast`/`+deep` modifier. This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

For complex features requiring design decisions, use `/eng-spec` instead.

## Task

$ARGUMENTS
