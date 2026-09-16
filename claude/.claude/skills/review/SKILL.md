---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

Thin wrapper over the `review-loop` agent: dispatch it, render the returned packet, raise the modals it cannot.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). Pass through to the agent verbatim.
- `+sec` / `+perf` / `+smell` — force that specialist pass; `no-specialist` — suppress it. All four pass through verbatim (step 1).

## Instructions

1. **Dispatch the loop**. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`. Pass, verbatim:
   - `mode: review-first`, `caller: review`
   - any `handoff:` block from `$ARGUMENTS` (schema: `~/.claude/skills/_shared/handoff-block.md`)
   - any `+fast` / `+deep` modifier and `iter=N`
   - any specialist flag from `$ARGUMENTS`: `+sec` / `+perf` / `+smell` or `no-specialist`
   - if `$ARGUMENTS` names a file path and no handoff block was given, scope the review to that file only

2. **Route on the returned `status`** — first match wins:

   - **`plan-impact`** → raise the modal (see below), then re-dispatch the loop with the user's decision and BOTH returned counters preserved (`iter` and `spec_iter`).
   - **`critical-blocker`** → STOP. Present `blockers` and wait for direction. Do NOT re-dispatch, do NOT `/fix`.
   - **`cap-reached`** → STOP. Report `findings_remaining`; the user decides. Do NOT `/fix`. The session stays `dirty`, so `git commit` stays blocked.
   - **`deferred`** → render the packet (step 3), add `findings_remaining` under `### Deferred to branch exit`, record convergence as for `converged`. Do NOT re-dispatch or `/fix` those items.
   - **`converged`** → render the packet (step 3), then `bash ~/.claude/scripts/review-gate-mark clean`. Mark ONLY on `converged` or `deferred`.

3. **Render the packet**, in this order:

   - `### Fixed` — every `fixed[]` entry (`finding`, `file_line`), `blocker` ones first and marked.
   - `### Perf findings` — its own heading, one entry per `perf[]` item with its `Principle:` line, regardless of disposition or auto-fix status.
   - `specialists` — one line naming which cross-cutting specialists ran (or that none matched / were suppressed).
   - `class_closure` — one line, ALWAYS, even `none` or `n/a`. If a `converged` packet lacks it, or it is a bare `none` that names no repaired finding, say the receipt is missing and do not render the run as clean.
   - `load_bearing_clean`, if present — one line.
   - `skipped_fp[]` — inline, each with its reason.
   - `nit[]` — inline, one combined line.

4. **Raise what the agent could not**. Present `ask[]`, each with its question; wait for direction. Never auto-fix an ask item.

   **Log each ask outcome** (PLAN-IMPACT asks excluded). After the user answers, one row per ask; telemetry never blocks:

   ```bash
   bash "$HOME/.claude/skills/review/log-review-finding" kind=finding \
     repo="$(basename "$(git rev-parse --show-toplevel)")" branch="$(git branch --show-current)" \
     lane=none scope=standalone phase=- iter=<iter from args, default 1> \
     gate=<entry gate> disposition=ask class=<entry class> file=<path> line=<n> \
     actioned=ask ask_outcome=<accepted|rejected|modified> desc="ask resolved: <one line>"
   ```

5. **If nothing is outstanding**: "No issues found that warrant auto-fix. Ready for `/commit`."

## Plan-impact findings (unskippable routing)

The agent defines `PLAN-IMPACT` and dispatches no coder on it.

1. Never fold it into the findings summary or triage it as an `ask`.
2. Present it via **AskUserQuestion** before any further dispatch: assumed →
   found → what changes, options `Adopt plan change` / `Keep plan as written` /
   `Discuss`.
3. Record the answer in the plan's `## Plan Deviations` section (create if
   absent): date, finding, decision, owner.
4. Re-dispatch `review-loop` with the decision and the preserved `iter` and `spec_iter`.

## Arguments

$ARGUMENTS
