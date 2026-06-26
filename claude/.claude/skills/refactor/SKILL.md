---
name: refactor
description: Smart refactorer — dispatches coder subagent(s), then auto-runs `/review`
allowed-tools: [Task, Read, Glob, Grep, Skill]
---

# Refactor

Analyze the code to refactor, determine whether it's frontend, backend, or fullstack, and dispatch the appropriate coder subagent(s).

## CRITICAL: Never modify a test to make a refactor pass

A refactor changes structure, not behavior — so the tests are the contract. **Never edit, weaken, or delete a test to get a refactor to pass.** Tests pin current behavior; modifying them mid-refactor masks the exact regressions a refactor is most likely to introduce. If you reach an issue that seems unsolvable without changing a test, **stop and alert the user** — do not work around it. Moving a test verbatim to a new file (no assertion changes) is safe.

## Modifiers

- `+fast` — Pass `model: "haiku"` to coder dispatches. Use for simple renames, extract-variable, or mechanical refactors.
- `+deep` — Dispatch the `-deep` coder variants (`backend-coder-deep` / `frontend-coder-deep`, Opus via frontmatter pin) and omit `model`. Use for complex refactors involving multiple interacting systems, subtle architectural changes, or tricky migration of patterns. Call-site `model: "opus"` is blocked by the agent-model-guard hook.

## Instructions

1. **Check for modifiers**: If `+deep` is present, swap each coder for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Analyze the refactoring target** described below:
   - Read the referenced files to understand the current code
   - Determine if this is a **frontend** refactor (components, pages, stores, styles), a **backend** refactor (models, controllers/views, services, middleware, migrations), or **both**
   - Identify the refactoring goal: structure, readability, performance, maintainability, pattern alignment

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls
   **Neither** (non-web repo) → Launch a single `coder` subagent

   For each coder:
   - Pass the refactoring description and any relevant context you gathered
   - Instruct it to: read and understand the existing code, implement the refactoring step by step, and ensure no functionality is broken
   - **Pass the CRITICAL test rule above verbatim**: never modify/weaken/delete a test to make the refactor pass; if blocked, stop and report back rather than touching a test (moving a test verbatim to a new file is fine)
   - If the refactor turns out to need architectural redesign, have it report back and recommend `/eng-spec` instead

4. **After coder(s) complete**, summarize:
   - What was refactored and why
   - What changed structurally
   - Any related concerns or follow-up items

5. **Auto-dispatch peer review**: After summarizing the refactor, tell the user: "Auto-dispatching `/review` to check the refactored code before committing." Build a handoff block from the coder output (same protocol as `/code`) and pass it as args so the reviewer doesn't re-derive scope from `git diff`:

   ```
   handoff:
   files: [<files the coder(s) reported changing>]
   tests-run: <what the coder(s) ran, or none>
   flagged: <anything the coder(s) flagged, or none>
   iter: 1
   ```

   Then invoke the `/review` skill using the Skill tool (`skill: "review"`, `args: <handoff block>`). If the user passed `+fast` or `+deep`, prepend the same modifier to the args (e.g., `args: "+fast\nhandoff: ..."`). This step runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

## Code to refactor

$ARGUMENTS
