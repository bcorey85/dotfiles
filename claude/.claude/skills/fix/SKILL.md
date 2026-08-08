---
name: fix
description: Dispatch coder subagents to fix review feedback (from a `/cc` comment handoff, a `/review` handoff, or the conversation), then auto-run `/review`. To act on inline comments left in `~/.claude/claude-comments.md`, use `/cc` — it reads them and routes here.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Fix Code Review Feedback

Thin wrapper. Fixing and the verification loop both live in the `review-loop`
agent (`~/.claude/agents/review-loop.md`), dispatched with `mode: fix-first`.
Your job is to hand it the findings, then render the packet it returns and
raise the modals it cannot.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). Pass through verbatim; the agent maps them to the coder variant and model.

## Instructions

1. **Dispatch the loop**. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (the agent is unpinned). Pass, verbatim:
   - `mode: fix-first`, `caller: fix`
   - the findings, from whichever source applies: `/cc` entries (`path`, `line`, `body`, `id` — highest priority, user-authored), a `/review` handoff block, or the conversation
   - any `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`), `iter=N`, and any `+fast` / `+deep` modifier
   - `no-review` if present — the agent then verifies via the execution gate and returns without a reviewer pass

   Invoked bare, with no findings in args and no handoff: if `~/.claude/claude-comments.md` may hold inline comments, point the user at `/cc` rather than parsing that file here. `/cc` owns reading and clearing it.

2. **Route on the returned `status`** — first match wins:

   - **`plan-impact`** → raise the modal (see `/review`'s "Plan-impact findings" section — same routing), then re-dispatch with the decision and BOTH returned counters preserved (`iter` and `spec_iter`).
   - **`critical-blocker`** → STOP. Present `blockers` and wait. Do NOT re-dispatch.
   - **`cap-reached`** → STOP. Report `findings_remaining`; the user decides. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`deferred`** → the one-round correctness budget was spent and the residue was logged for branch exit. A normal completion, not a stop: render the packet (step 3), add `findings_remaining` under `### Deferred to branch exit`, and record convergence as for `converged`. Do NOT re-dispatch to chase them; `/branch-recap` reads them back.
   - **`converged`** → render the packet (step 3), then record convergence: `bash ~/.claude/scripts/review-gate-mark clean`. Run the mark ONLY for a packet whose `status` is `converged` or `deferred` — the other statuses leave the commit gate dirty by design.

3. **Log walkthrough escapes — MANDATORY on `converged`, do not skip.** When the findings came from **the user, in conversation**, on code a prior `/review` already blessed, each one is ground truth: the human caught what the gates passed. This is the highest-volume escape source in the toolkit and the only one that fires without a dedicated skill invocation — treat it as a hard gate before rendering, not a trailing nicety.

   Fires only when ALL hold:
   - `status: converged` or `deferred`, and the fix was actually applied (not skipped as a false positive, not deferred)
   - the finding came from the **conversation** — NOT from a `/review` handoff block (those are the loop's own catches, already counted in `review-metrics.jsonl`; logging them again would double-count against the loop) and NOT from `/cc` (it logs `stage_found=cc` itself in its step 7 — logging here too would duplicate every comment)
   - the code under fix was already through `/review` on this branch — a first-pass fix on net-new code is not an escape
   - it is a defect, not a new requirement or a change of direction. A gate cannot miss information it never had.

   One line per distinct defect, no user prompt, do not pause:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=walkthrough gate_missed=<review|drift-gate|test-intent|stage|coder> class=<bug|smell|duplication|plan-drift|test-gap|other> severity=<high|medium|low> lane=<eng-spec|code|other> guard=<...> desc="<one line>" file=<path>
   ```

   `guard` is the ratchet rung from `~/.claude/skills/_shared/escape-ratchet.md`. Pick it here without pausing; state the proposed guard in the packet (step 3) and apply it on approval there rather than prompting mid-log.

   Classify from the finding itself; when unsure, `class=other`. Infer `lane` from the branch's planning artifacts (eng-spec doc → `eng-spec`, direct dispatch → `code`); ask only when genuinely ambiguous. If the script fails, mention it and continue — telemetry never blocks a fix.

4. **Render the packet**: `### Fixed` from `fixed[]` with `blocker` items first and marked; `skipped_fp[]` with reasons; `perf[]` under its own heading with `Principle:` lines; `nit[]` inline. If any finding needs architectural rethinking, recommend `/eng-spec`.

5. **Raise what the agent could not**. Present `ask[]` with each question; wait for direction. Never auto-fix an ask item.

## Arguments

$ARGUMENTS
