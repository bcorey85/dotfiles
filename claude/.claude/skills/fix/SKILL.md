---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Fix Code Review Feedback

Thin wrapper over the `review-loop` agent (`mode: fix-first`): hand it the findings, render the returned packet, raise the modals it cannot.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). Pass through verbatim.

## Instructions

1. **Dispatch the loop**. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: fix-first`, `caller: fix`
   - the findings, from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation
   - any `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`), `iter=N`, and any `+fast` / `+deep` modifier
   - `no-review` if present — the agent then verifies via the execution gate and returns without a reviewer pass

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing that file here.

2. **Route on the returned `status`** — first match wins:

   - **`plan-impact`** → raise the modal (see `/review`'s "Plan-impact findings" section — same routing), then re-dispatch with the decision and BOTH returned counters preserved (`iter` and `spec_iter`).
   - **`critical-blocker`** → STOP. Present `blockers` and wait. Do NOT re-dispatch.
   - **`cap-reached`** → STOP. Report `findings_remaining`; the user decides. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`deferred`** → render the packet (step 3), add `findings_remaining` under `### Deferred to branch exit`, record convergence as for `converged`. Do NOT re-dispatch.
   - **`converged`** → render the packet (step 3), then `bash ~/.claude/scripts/review-gate-mark clean`. Mark ONLY on `converged` or `deferred`.

3. **Log walkthrough escapes — MANDATORY on `converged`, do not skip.** When the findings came from **the user, in conversation**, on code a prior `/review` already blessed, log each one.

   Fires only when ALL hold:
   - `status: converged` or `deferred`, and the fix was actually applied (not skipped as a false positive, not deferred)
   - the finding came from the **conversation** — NOT from a `/review` handoff block and NOT from `/cc`
   - the code was already through `/review` on this branch
   - it is a defect, not a new requirement or a change of direction

   One line per distinct defect, no user prompt, do not pause:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=walkthrough gate_missed=<review|drift-gate|test-intent|stage|coder|eng-spec> class=<bug|smell|duplication|plan-drift|test-gap|other> severity=<high|medium|low> lane=<eng-spec|code|other> guard=<...> desc="<one line>" file=<path>
   ```

   `guard` is the ratchet rung from `~/.claude/skills/_shared/escape-ratchet.md`. Pick it here without pausing; state the proposed guard in the packet (step 3) and apply it on approval there.

   Classify from the finding itself (`class=other` when unsure); infer `lane` from planning artifacts (eng-spec doc → `eng-spec`, else `code`). A failed log never blocks the fix — mention it and continue.

4. **Render the packet**: `### Fixed` from `fixed[]` with `blocker` items first and marked; `skipped_fp[]` with reasons; `perf[]` under its own heading with `Principle:` lines; `nit[]` inline. If any finding needs architectural rethinking, recommend `/eng-spec`.

5. **Raise what the agent could not**. Present `ask[]` with each question; wait for direction. Never auto-fix an ask item.

   **Log each ask outcome** (PLAN-IMPACT asks excluded). After the user answers, one row per ask; telemetry never blocks:

   ```bash
   bash "$HOME/.claude/skills/review/log-review-finding" kind=finding \
     repo="$(basename "$(git rev-parse --show-toplevel)")" branch="$(git branch --show-current)" \
     lane=<eng-spec|code|other, per step 3> scope=standalone phase=- iter=<returned iter> \
     gate=<entry gate> disposition=ask class=<entry class> file=<path> line=<n> \
     actioned=ask ask_outcome=<accepted|rejected|modified> desc="ask resolved: <one line>"
   ```

6. **Aikido PR-comment replies — post disposition back to the bot.** Fires only for findings that are Aikido PR comments: `author` is `aikido-pr-checks[bot]` (or the body carries `@AikidoSec` / `app.aikido.dev`) AND the finding carries a `comment_id`. Skip this step entirely when no such findings are present, or when no `comment_id` is available. Match packet entries to comments by `(path, line)`:

   - **Fixed** (entry in `fixed[]`, fix actually applied) → reply `Fixed.` plus a one-line note of what changed.
   - **Not relevant** (entry in `skipped_fp[]`, ruled a false positive) → reply `@AikidoSec ignore: <reason>` using the FP reason, verbatim in that form.
   - Anything else (deferred, nit, ask, cap-reached residue) → no auto-reply; leave for the human.

   Post each reply to the review-comment thread:

   ```bash
   repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
   pr=$(gh pr view --json number --jq '.number')
   gh api --method POST "repos/$repo/pulls/$pr/comments/<comment_id>/replies" -f body='<reply>'
   ```

   Best-effort: a failed reply never blocks the fix or the commit gate — report it and continue. List posted replies under `### Aikido replies` in the packet.

## Arguments

$ARGUMENTS
