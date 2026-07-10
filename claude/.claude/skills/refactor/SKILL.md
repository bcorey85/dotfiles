---
name: refactor
description: Smart refactorer — dispatches coder subagent(s), then auto-runs `/review`. With no arguments, audits the ENTIRE branch diff for code smells and fixes them without asking for focus. Use for "refactor X", "clean up X", "second pass", or an end-of-branch cleanup sweep on code we own.
allowed-tools: [Agent, Bash, Read, Glob, Grep, Skill]
---

# Refactor

Analyze the code to refactor, determine whether it's frontend, backend, or fullstack, and dispatch the appropriate coder subagent(s).

## CRITICAL: Never modify a test to make a refactor pass

A refactor changes structure, not behavior — so the tests are the contract. **Never edit, weaken, or delete a test to get a refactor to pass.** Tests pin current behavior; modifying them mid-refactor masks the exact regressions a refactor is most likely to introduce. If you reach an issue that seems unsolvable without changing a test, **stop and alert the user** — do not work around it. Moving a test verbatim to a new file (no assertion changes) is safe.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` for simple renames, extract-variable, or mechanical refactors; `+deep` for refactors involving multiple interacting systems, subtle architectural changes, or tricky pattern migrations.

## Instructions

1. **Check for modifiers**: If `+deep` is present, swap each coder for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Determine the mode and analyze the target**:

   **Branch audit mode (the default)** — when `$ARGUMENTS` is empty or generic ("cleanup", "final pass", "second pass", "the branch"): the target is the entire branch diff. Do NOT ask what to focus on — the focus is defined by the smell checklist below. Scope with `git diff --stat main...HEAD` (fall back to `master` if no `main`), read the changed files, and sweep them for every item on the checklist:

   - **Duplication** introduced across the branch's commits — same logic grown in two places by separate tasks; extract it
   - **Dead code left by iteration** — orphaned helpers, unused exports/imports/params, branches whose call sites were deleted
   - **Naming drift** — names that no longer match what the thing became as the branch evolved
   - **Speculative abstraction** — generality nothing uses (single-implementation interfaces, unused options/flags); inline it
   - **Wrong-altitude code** — business logic in routes/components/handlers, formatting or presentation in services
   - **Comment rot and scaffolding** — stale comments, commented-out code, leftover debug logging, TODO litter
   - **Pattern misalignment** — changed code that diverges in idiom from the surrounding files that did NOT change
   - **Oversized units** — functions/components that accreted multiple responsibilities across commits; split them

   Compile the findings into a concrete work list before dispatching. Present it as a statement of what you're fixing, not a question. Only come back to the user if the branch diff is empty or the sweep genuinely finds nothing — in that case say so and stop.

   **Targeted mode** — when `$ARGUMENTS` names specific code or a specific goal:
   - Read the referenced files to understand the current code
   - Identify the refactoring goal: structure, readability, performance, maintainability, pattern alignment

   In both modes, determine if the work is **frontend** (components, pages, stores, styles), **backend** (models, controllers/views, services, middleware, migrations), or **both**.

3. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Agent tool calls
   **Neither** (non-web repo) → Launch a single `coder` subagent

   For each coder:
   - Pass the refactoring description (in branch audit mode: the compiled work list, with file paths per finding) and any relevant context you gathered
   - Instruct it to: read and understand the existing code, implement the refactoring step by step, and ensure no functionality is broken
   - **Pass the CRITICAL test rule above verbatim**: never modify/weaken/delete a test to make the refactor pass; if blocked, stop and report back rather than touching a test (moving a test verbatim to a new file is fine)
   - If the refactor turns out to need architectural redesign, have it report back and recommend `/eng-spec` instead

4. **After coder(s) complete**, summarize:
   - What was refactored and why
   - What changed structurally
   - Any related concerns or follow-up items

   **Log escapes**: if the refactor target is code produced by this branch's coding loop (i.e., `/code` + `/review` already blessed it), each distinct smell the refactor fixed is a miss by the quality layer. Log one line per distinct smell (not per file):

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=refactor gate_missed=review class=<smell|duplication> severity=medium lane=<deep-plan|eng-spec|code|other> desc="<one line>" file=<representative path>
   ```

   `lane` is the planning lane that produced the branch's work — infer from the conversation or planning artifacts (deep-plan task dir → `deep-plan`, eng-spec doc → `eng-spec`, direct dispatch → `code`). Skip logging when the target is legacy code that never went through the loop — old debt is not an escape.

5. **Mandatory test audit** (every refactor, no exceptions): After the coder(s) complete, dispatch a `test-reviewer` subagent (`model: "sonnet"`) to audit the test suite touching the refactored code. A refactor's whole safety guarantee rests on the tests, so this runs even when no test files changed — a refactor that leaves behind weakened assertions, stale tests, or newly-uncovered branches is exactly what this catches.
   - Pass the refactor scope as the target (backend / frontend / the specific module(s) refactored) so the reviewer narrows to the relevant suite.
   - Pass the list of files the coder(s) changed so it can check coverage of the refactored code specifically.
   - Surface its findings in your summary. If it flags weakened assertions or tests that appear altered to accommodate the refactor, treat that as a violation of the CRITICAL test rule above — stop and alert the user rather than proceeding to commit.

   Never skip this step, even under `+fast`.

6. **Auto-dispatch peer review**: After summarizing the refactor, tell the user: "Auto-dispatching `/review` to check the refactored code before committing." Build a handoff block from the coder output (same protocol as `/code`) and pass it as args so the reviewer doesn't re-derive scope from `git diff`:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what was refactored and why>
     tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
     flagged: <anything the coder(s) flagged, or "none">
     plan_impact: <verbatim PLAN-IMPACT block from a coder report, or "none">
     iter: 1
   ```

   Then invoke the `/review` skill using the Skill tool (`skill: "review"`, `args: <handoff block>`). If the user passed `+fast` or `+deep`, prepend the same modifier to the args (e.g., `args: "+fast\nhandoff: ..."`). This step runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

## Code to refactor

$ARGUMENTS
