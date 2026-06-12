---
name: code
description: Dispatch coder subagent(s) for implementation, then auto-run `/review` — auto-detects scope or accepts be/fe/fs modifier
allowed-tools: [Task, Read, Glob, Grep, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope
- `+fast` — Pass `model: "haiku"` to coder dispatches. For trivial tasks like renames, typos, or simple one-line changes.
- `+deep` — Dispatch the `-deep` coder variants (`backend-coder-deep` / `frontend-coder-deep`, Opus via frontmatter pin) and omit `model`. For complex tasks requiring deeper reasoning. Call-site `model: "opus"` is blocked by the agent-model-guard hook.

## Instructions

1. **Check for modifiers**: If `+deep` is present, swap each coder for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Detect multi-phase plans (MANDATORY check)**: If the task input is a path to a plan file (e.g., `*-plan.md` under `docs/eng-specs/`) or pasted plan content, read it and check whether it contains multiple `## Phase N:` sections.

   **If it's a multi-phase plan:**
   - Do NOT dispatch all phases at once.
   - Identify the next un-executed phase by reading the plan's `## Phase Status` section: the first unchecked (`- [ ]`) entry is the phase to dispatch. This is the source of truth across `/clear` boundaries — do NOT scan git log or diff to figure out where you are. If the plan has no `## Phase Status` section (older plan format), fall back to `git status` + per-phase success criteria, but flag this to the user so they can backfill the section.
   - Dispatch the coder for THAT ONE PHASE ONLY. The coder must run the phase's "Automated Verification" gate (typically `npm run validate` or equivalent) before returning.
   - After the coder completes and you summarize, auto-dispatch `/review` (step 5).
   - After peer review passes, mark the phase done in the plan: `Edit` the `## Phase Status` section to flip `- [ ] Phase N: ...` → `- [x] Phase N: ...`. This single Edit is the durable record across `/clear`.
   - Then stop and print the phase-complete block (see "Phase-Complete Block" below) with all placeholders resolved. Do NOT proceed to the next phase without explicit user sign-off. Clearing between phases is the default — the orchestrator re-enters by reading the plan's `## Phase Status` section, which is cheaper than letting context auto-compact mid-build.
   - If the plan has only one phase or no phase headers, treat it as a single dispatch (skip the phase loop).

3. **Determine scope**:
   - If a scope modifier (`be`, `fe`, `fs`) was provided, use that
   - Otherwise, analyze the task description — read referenced files, check relevant directories — and determine if this is frontend, backend, both, or neither (non-web repo: CLI tool, library, scripts, infra, config)

4. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Task tool calls
   **Neither** (non-web repo) → Launch a single `coder` subagent — the frontend/backend split only applies to web-fullstack codebases

   For each coder:
   - Pass the full task description and any relevant context
   - Instruct it to follow existing patterns in the codebase
   - Write tests if needed
   - Flag any ambiguities or issues
   - If the task turns out to be architectural, have it report back and recommend `/eng-spec` instead

5. **After coder(s) complete**, summarize for the user AND build a handoff block for downstream review.

   User summary:
   - What was implemented
   - Any issues flagged
   - Any follow-up items

   Handoff block (passed as args to `/review` in step 5). Schema is defined in `review/SKILL.md` under "Handoff Block". Required fields:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what changed and why>
     tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
     flagged: <issues the coder explicitly flagged, or "none">
     iter: 1
   ```

   The handoff lets the reviewer skip rediscovery — file scope, change intent, and test status are upstream context the reviewer no longer has to reconstruct via `git diff` and full re-reads. Coders already know all of this; pass it forward instead of forcing re-discovery.

6. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching `/review` to check the implementation before committing." Then invoke the `/review` skill via the Skill tool with `skill: "review"` and `args` containing the handoff block from step 5 plus any `+fast`/`+deep` modifier. This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

7. **Multi-phase plans only — pause for sign-off**: If step 2 detected a multi-phase plan, after `/review` returns, stop and print the phase-complete block (see below) with all placeholders resolved. Do not auto-advance. When the user replies to continue (in a fresh context after `/clear`, or in the same context if they skipped clearing), re-enter at step 2 with the next phase — use `git status` and the plan's success criteria to detect what's already done.

## Phase-Complete Block

After each phase + review completes, print this block verbatim with `<N>`, `<N+1>`, `<plan-path>`, and the manual-verification list filled in from the just-finished phase. The user copy-pastes the slash command after `/clear`.

```
Phase <N> complete. Auto-advance is OFF.

Manual verification (from the plan):
- <item 1 from phase's Manual Verification>
- <item 2>
- <...>

Next:
  1. Run the manual verification above.
  2. /clear
  3. Paste: /code <plan-path> continue

Or give feedback now (before clearing) for revisions to phase <N>.
```

Resolution rules:

- `<N>` and `<N+1>` are the just-finished and next phase numbers.
- `<plan-path>` is the absolute or repo-relative path the orchestrator was invoked with.
- Manual-verification items come from the just-finished phase's `#### Manual Verification:` section in the plan. If that section is empty, omit the bulleted list and replace step 1 with: "Spot-check the diff."
- If this was the LAST phase, replace the "Next" block with: "All phases complete. Review the diff and open a PR when ready."

For complex features requiring design decisions, use `/eng-spec` instead.

## Task

$ARGUMENTS
