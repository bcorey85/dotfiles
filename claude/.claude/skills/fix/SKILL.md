---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
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

   a. **Args from `/cc`** — inline comments the user authored in `~/.claude/claude-comments.md` (Neovim `<leader>cc` → `:ClaudeReviewComment`), passed in as an entry list (`path`, `line`, `body`, `id`). These are explicit user-authored requests at the **highest priority** — not heuristic findings. `/cc` owns reading and clearing `claude-comments.md`; this skill just fixes the entries it hands over. Do not read or rewrite `claude-comments.md` here.

   b. **Args from `/review`** — if invoked via the review handoff, the issues list is passed in args.

   c. **The conversation** — any review findings discussed above.

   If invoked bare with none of these sources, but `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing the file here.

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
