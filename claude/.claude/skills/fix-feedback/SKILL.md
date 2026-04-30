---
name: fix-feedback
description: Dispatch coder subagents to fix review feedback, then auto-run peer review
allowed-tools: [Task, Read, Glob, Grep, Skill]
---

# Fix Code Review Feedback

Dispatch parallel frontend-coder and backend-coder subagents to investigate and resolve valid issues from the most recent code review.

## Modifiers

- `+fast` — Use Haiku model for coder subagents. Use when review findings are trivial (typos, simple style fixes).
- `+deep` — Use Opus model for coder subagents. Use for complex review findings that require deeper reasoning to fix correctly.

## Instructions

1. **Parse args**:
   - **Modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt.
   - **Iteration counter**: Look for `iter=N` in args (default `iter=1`). Hold this value — when re-invoking `/peer-review` in step 5, pass `iter=N+1` so the loop is bounded.

2. **Parse the review feedback** from the conversation (and from args, if `/peer-review` passed an issues list) to categorize issues by which coder owns the file (frontend vs backend, or whichever split applies to this codebase)

3. **Launch coder agents in parallel** using a single message with multiple Task tool calls.

   **Common instructions for every coder dispatched here** (include verbatim in the prompt):

   > Fix only the issues listed below. Do not refactor surrounding code. Do not "improve" things you notice along the way. Do not rename, restructure, or add abstractions that aren't required by the fix itself. A focused 5-line fix is the right output, not a 50-line cleanup PR.
   >
   > After fixing each issue, check all callers and consumers of the changed code. If a fix changes a method signature, return type, or behavioral contract, update every caller in the same pass. Do not leave callers out of sync.
   >
   > If a listed issue turns out to be a false positive on inspection, skip it and report why. Do not "fix" issues that aren't actually broken just because the reviewer flagged them.

   **Frontend Coder** (`subagent_type: frontend-coder`):
   - Pass all frontend-specific issues with file paths and line numbers
   - Include enough context from the review for the coder to understand the problem
   - Apply the common instructions above

   **Backend Coder** (`subagent_type: backend-coder`):
   - Pass all backend-specific issues with file paths and line numbers
   - Include enough context from the review for the coder to understand the problem
   - Apply the common instructions above

   If all issues are frontend-only or backend-only, launch only the relevant coder agent.

4. **After coders complete**, summarize for the user AND build a handoff block for the verification reviewer.

   User summary:
   - Which issues were fixed
   - Any issues intentionally skipped (with reasoning)
   - Any new concerns discovered
   - If any issue requires architectural rethinking, recommend the user run `/eng-spec` instead

   Handoff block (passed as args to `/peer-review` in step 5). Schema is defined in `peer-review/SKILL.md` under "Handoff Block". Required fields:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what fix was applied>
     tests-run: <command(s) and pass/fail status, or "none">
     prior-issues:
       - issue: <one line from prior review>
         status: fixed | skipped | partial
         file: <path>
     flagged: <new concerns from this fix pass, or "none">
     iter: <N+1 — incremented from incoming iter>
   ```

   The `prior-issues` list scopes the verification reviewer to "did these fixes take?" first, before any new-issue scan. This is the main token saving — the reviewer no longer re-reviews untouched code.

5. **Auto-dispatch peer review**: After summarizing the fixes, tell the user: "Auto-dispatching `/peer-review` to verify the fixes before committing (iteration N+1 of 3)." Then invoke the `/peer-review` skill via the Skill tool with `skill: "peer-review"` and `args` containing the handoff block from step 4 plus `iter=N+1` and any `+fast`/`+deep` modifier. This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs.

## Validation

Each agent should verify issues are valid before fixing. Skip issues that are:

- False positives or stylistic preferences
- Out of scope for a quick fix
- Blocked by other unresolved issues
- Architectural in nature (recommend `/eng-spec` instead)
