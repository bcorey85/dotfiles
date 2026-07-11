---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools: [Agent, Bash, Read, Edit, AskUserQuestion]
---

# Code Review

Thin wrapper. The review→fix convergence loop lives in the `review-loop` agent
(`~/.claude/agents/review-loop.md`) so its instructions never enter this
context. Your job is to dispatch it, then render the packet it returns and
raise the modals it cannot.

## Modifiers

- `+fast` / `+deep` — semantics in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). Pass through to the agent verbatim; it maps them to the reviewer variant and model.

## Instructions

1. **Dispatch the loop**. `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (the agent is unpinned). Pass, verbatim:
   - `mode: review-first`, `caller: review`
   - any `handoff:` block from `$ARGUMENTS` (schema: `~/.claude/skills/_shared/handoff-block.md`)
   - any `+fast` / `+deep` modifier and `iter=N`
   - if `$ARGUMENTS` names a file path and no handoff block was given, scope the review to that file only

2. **Route on the returned `status`** — first match wins:

   - **`plan-impact`** → raise the modal (see below), then re-dispatch the loop with the user's decision and the returned `iter` preserved.
   - **`critical-blocker`** → STOP. Present `blockers` and wait for direction. Do NOT re-dispatch, do NOT `/fix`.
   - **`cap-reached`** → STOP. Report `findings_remaining`; the user decides. Do NOT `/fix`. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`converged`** → render the packet (step 3).

3. **Render the packet**, in this order:

   - `### Findings by severity` — every `fixed[]` entry (`severity`, `finding`, `file_line`). The loop repaired these; the user must still learn what they were. An empty `fixed[]` on `iter > 1` is a bug in the agent, not a clean run.
   - `### Perf findings` — its own heading, one entry per `perf[]` item with its `Principle:` line. These never scroll past silently, regardless of severity or auto-fix status; the user is deliberately building backend-performance intuition from them.
   - `load_bearing_clean`, if present — one line.
   - `medium.fix` — applied, one line each. `medium.skip` — inline with its reason.
   - `low[]` and notes — inline.

4. **Raise what the agent could not**. Present `medium.ask`; wait for direction. Never auto-fix an ambiguous item — when the right call needs a design decision, auto-fixing is most wrong.

5. **If nothing is outstanding**: "No issues found that warrant auto-fix. Ready for `/commit`."

## Plan-impact findings (unskippable routing)

A finding that **invalidates a plan/design decision** — not a defect, but
evidence the plan's assumption is wrong (missed contract/invariant, mis-tiered
risk, ungated security surface) — is a `PLAN-IMPACT`, not a severity bucket.
The agent returns `status: plan-impact` and dispatches no coder. Then:

1. Never fold it into the findings summary or triage it as a MEDIUM.
2. Present it via **AskUserQuestion** before any further dispatch: assumed →
   found → what changes, options `Adopt plan change` / `Keep plan as written` /
   `Discuss`. The modal blocks until answered — that is the point.
3. Record the answer in the plan's `## Plan Deviations` section (create if
   absent): date, finding, decision, owner. `/verify` reconciles against the
   amended plan; `/finalize`'s ADR inherits it.
4. Re-dispatch `review-loop` with the decision and the preserved `iter`.

## Arguments

$ARGUMENTS
