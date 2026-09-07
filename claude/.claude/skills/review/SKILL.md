---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

Thin wrapper over the `review-loop` agent (its instructions never enter this context): dispatch it, render the returned packet, raise the modals it cannot.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). Pass through to the agent verbatim; it maps them to the reviewer variant and model.
- `+sec` / `+perf` / `+smell` — force that specialist pass; `no-specialist` — suppress it. All four pass through verbatim (step 1).

## Instructions

1. **Dispatch the loop**. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (the agent is unpinned). Pass, verbatim:
   - `mode: review-first`, `caller: review`
   - any `handoff:` block from `$ARGUMENTS` (schema: `~/.claude/skills/_shared/handoff-block.md`)
   - any `+fast` / `+deep` modifier and `iter=N`
   - any specialist flag from `$ARGUMENTS`: `+sec` / `+perf` / `+smell` (force that cross-cutting specialist pass) or `no-specialist` (suppress it). Absent these, the loop's Step 6b decides per its deterministic file-path/content/diff-size trigger.
   - if `$ARGUMENTS` names a file path and no handoff block was given, scope the review to that file only

2. **Route on the returned `status`** — first match wins:

   - **`plan-impact`** → raise the modal (see below), then re-dispatch the loop with the user's decision and BOTH returned counters preserved (`iter` and `spec_iter`).
   - **`critical-blocker`** → STOP. Present `blockers` and wait for direction. Do NOT re-dispatch, do NOT `/fix`.
   - **`cap-reached`** → STOP. Report `findings_remaining`; the user decides. Do NOT `/fix`. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`deferred`** → one-round budget spent, residue logged for branch exit. A normal completion: render the packet (step 3), add `findings_remaining` under `### Deferred to branch exit`, record convergence as for `converged`. Do NOT re-dispatch or `/fix` those items; `/branch-recap` reads them back.
   - **`converged`** → render the packet (step 3), then `bash ~/.claude/scripts/review-gate-mark clean`. Mark ONLY on `converged` or `deferred` — other statuses leave the gate dirty by design.

3. **Render the packet**, in this order:

   - `### Fixed` — every `fixed[]` entry (`finding`, `file_line`), `blocker` ones first and marked. An empty `fixed[]` on `iter > 1` is a bug in the agent, not a clean run.
   - `### Perf findings` — its own heading, one entry per `perf[]` item with its `Principle:` line. Render every entry regardless of disposition or auto-fix status.
   - `specialists` — one line naming which cross-cutting specialists ran (or that none matched / were suppressed). Security findings, if any, already appear in `fixed[]`/`blockers`/`ask[]`.
   - `class_closure` — one line, ALWAYS, even `none` or `n/a`: the loop's stopping-rule receipt. A `converged` packet missing it is an agent bug — say so, don't render as clean. A bare `none` that names no repaired finding is an unrun check, not a receipt.
   - `load_bearing_clean`, if present — one line.
   - `skipped_fp[]` — inline, each with its reason.
   - `nit[]` — inline, one combined line.

4. **Raise what the agent could not**. Present `ask[]`, each with its question; wait for direction. Never auto-fix an ask item — when the right call needs a design decision, auto-fixing is most wrong.

5. **If nothing is outstanding**: "No issues found that warrant auto-fix. Ready for `/commit`."

## Plan-impact findings (unskippable routing)

The agent defines `PLAN-IMPACT` (see `~/.claude/agents/review-loop.md`) and dispatches no coder on it. Your job starts there:

1. Never fold it into the findings summary or triage it as an `ask`.
2. Present it via **AskUserQuestion** before any further dispatch: assumed →
   found → what changes, options `Adopt plan change` / `Keep plan as written` /
   `Discuss`. The modal blocks until answered — that is the point.
3. Record the answer in the plan's `## Plan Deviations` section (create if
   absent): date, finding, decision, owner. `/verify` reconciles against the
   amended plan; `/adr` inherits it.
4. Re-dispatch `review-loop` with the decision and the preserved `iter` and `spec_iter`.

## Arguments

$ARGUMENTS
