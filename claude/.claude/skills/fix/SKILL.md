---
name: fix
description: Dispatch coder subagents to fix review feedback (from `.claude/review.md`, the conversation, or a `/review` handoff), then auto-run `/review`
allowed-tools: [Task, Bash, Read, Glob, Grep, Skill]
---

# Fix Code Review Feedback

Dispatch parallel frontend-coder and backend-coder subagents to investigate and resolve valid issues from the most recent code review.

## Modifiers

- `+fast` — Pass `model: "haiku"` to coder dispatches. Use when review findings are trivial (typos, simple style fixes).
- `+deep` — Dispatch the `-deep` coder variants (`backend-coder-deep` / `frontend-coder-deep`, Opus via frontmatter pin) and omit `model`. Use for complex review findings that require deeper reasoning to fix correctly. Call-site `model: "opus"` is blocked by the agent-model-guard hook.

## Instructions

1. **Parse args**:
   - **Modifiers**: If `+deep` is present, swap each coder for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt.
   - **Iteration counter**: Look for `iter=N` in args (default `iter=1`). Hold this value — when re-invoking `/review` in step 5, pass `iter=N+1` so the loop is bounded.
   - **One-shot mode**: If `iter=oneshot` is present, this invocation is the post-convergence MEDIUM triage from `/review` — NOT part of the iter-bounded loop. Do not increment. In step 5, pass `iter=oneshot` to `/review` so it performs a single verification pass and stops without re-triaging MEDIUMs.

2. **Parse the review feedback** from these sources (in order), then categorize issues by which coder owns the file (frontend vs backend, or whichever split applies to this codebase):

   a. **`~/.claude/review.md`** (global, shared across all repos) — inline comments left by the user from diffview.nvim (`<leader>dc`). These are explicit user-authored requests at the highest priority — not heuristic findings. Use the bundled script for ALL reading and rewriting; do NOT parse or rewrite the file by hand:

   1. List in-scope entries:

      ```bash
      bash "${CLAUDE_SKILL_DIR}/review-md-consume" list "$(git rev-parse --show-toplevel)"
      ```

      Returns fresh (≤48h), current-repo entries as JSON (`[{id, path, line, timestamp, body}]`). Stale in-scope entries are counted on stderr — note the count in the summary. Entries from other repos are never listed or touched.

   2. After dispatching and triaging, clear what was handled:

      ```bash
      bash "${CLAUDE_SKILL_DIR}/review-md-consume" resolve "$(git rev-parse --show-toplevel)" <id>...
      ```

      Pass the `id` of every entry that was **resolved** (fix attempted) or **skipped after triage** (false positive, intentional, out of scope — note skip reasons in the summary). Do NOT pass ids of **deferred** entries (recommended `/eng-spec`, waiting on user input) — they stay in the file for the next run. The script re-reads the file at resolve time, so entries added by another nvim session in the meantime are preserved, and it deletes the file when nothing remains.

   b. **Args from `/review`** — if invoked via the review handoff, the issues list is passed in args.

   c. **The conversation** — any review findings discussed above.

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

   If all issues are frontend-only or backend-only, launch only the relevant coder agent. In non-web repos where the frontend/backend split doesn't apply, dispatch a single `coder` subagent with all issues.

4. **After coders complete**, summarize for the user AND build a handoff block for the verification reviewer.

   User summary:
   - Which issues were fixed
   - Any issues intentionally skipped (with reasoning)
   - Any new concerns discovered
   - If any issue requires architectural rethinking, recommend the user run `/eng-spec` instead

   Handoff block (passed as args to `/review` in step 5). Schema is defined in `review/SKILL.md` under "Handoff Block". Required fields:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what fix was applied>
     tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
     prior-issues:
       - issue: <one line from prior review>
         status: fixed | skipped | partial
         file: <path>
     flagged: <new concerns from this fix pass, or "none">
     iter: <N+1 — incremented from incoming iter>
   ```

   The `prior-issues` list scopes the verification reviewer to "did these fixes take?" first, before any new-issue scan. This is the main token saving — the reviewer no longer re-reviews untouched code.

5. **Auto-dispatch peer review**: After summarizing the fixes, invoke the `/review` skill via the Skill tool with `skill: "review"` and `args` containing the handoff block from step 4 plus the iter value and any `+fast`/`+deep` modifier.
   - **Normal (loop) mode**: Tell the user "Auto-dispatching `/review` to verify the fixes before committing (iteration N+1 of 3)." Pass `iter=N+1`.
   - **One-shot mode** (incoming `iter=oneshot`): Tell the user "Auto-dispatching `/review` for one final verification of the MEDIUM fixes." Pass `iter=oneshot`. `/review` will run a single verification pass and stop without re-triaging.

   This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs.

## Validation

Each agent should verify issues are valid before fixing. Skip issues that are:

- False positives or stylistic preferences
- Out of scope for a quick fix
- Blocked by other unresolved issues
- Architectural in nature (recommend `/eng-spec` instead)
