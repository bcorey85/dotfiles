---
name: escape
description: Log a defect that escaped the automated loop — caught by human PR reading, in production, or anywhere downstream of the gates. Appends to `~/.claude/review-escapes.jsonl`, the ground-truth side of the review flywheel (aggregated by /audit review). Triggers on "log escape", "the loop missed this", "this got past review", "/escape", and "log these over-engineering findings".
allowed-tools: [Bash, Read, Glob, Grep, Edit]
---

# Log an Escape

One escape = one defect found downstream of the gate that should have caught it. `/cc`, `/fix` (conversation-sourced findings, as `stage_found=walkthrough`), `/refactor`, and `/verify` log their own escapes automatically; this skill is the manual channel for everything else — things you catch reading a PR, a prod bug traced back to loop output, a smell noticed weeks later.

## Instructions

1. **Extract the fields** from `$ARGUMENTS` and the conversation:
   - `stage_found` — where the defect surfaced: `walkthrough` (you, reading `/stage`'s queue at a phase sign-off — inside the loop), `phase-gate` (a downstream agent caught it inside the phase loop, before you read anything), `pr-human` (you, reading the diff after it left the gates), `prod`, `verify`, `other`
   - `gate_missed` — which layer should have caught it: `review` (bugs/quality), `drift-gate` (plan drift), `test-intent` (bug-pinning tests), `stage` (bug in a mechanically-staged SAFE-tier file — the invariant failed), `coder` (should never have been written), `eng-spec` (**the defect was in the plan** — an unrunnable criterion, a criterion contradicting the domain, a mandated primitive with unstated semantics. Use this whenever the implementation faithfully matched a wrong spec: no reviewer can catch that, because it checks the diff against the spec and finds them in agreement. Never file it under `coder`.)
   - `class` — `bug` | `smell` | `duplication` | `complexity` | `plan-drift` | `test-gap` | `other` (`complexity` = code that need not have existed, the `/refactor simplify` class)
   - `severity` — `high` | `medium` | `low`
   - `desc` — one line, specific enough to be legible in 3 months
   - `file` — representative path, if known
   - `lane` — optional: planning lane that produced the work (`eng-spec` | `code` | `other`); ask if the conversation makes it ambiguous — this feeds the lane-level A/B evidence in /audit review

   If the description is too vague to classify, ask ONE clarifying question — a mislabeled escape pollutes the very data this exists to produce. A new requirement or changed mind is NOT an escape; only log things a gate should have caught with the information it had.

2. **Ratchet** — run the guard decision per `~/.claude/skills/_shared/escape-ratchet.md` (including its ADR addendum) and carry the chosen rung into the log line below.

3. **Log it**:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")" stage_found=<...> gate_missed=<...> class=<...> severity=<...> lane=<...> guard=<...> desc="<...>" file=<...>
   ```

4. **Confirm** by echoing the logged fields and the guard decision, then stop. This skill never fixes the defect itself — route fixes through `/fix`.

## Batch mode: an over-engineering review's finding list

Triggered by `/escape ponytail` (or any request to log a complexity review's
findings). Use it when a review whose only lens is unnecessary complexity has
just printed a tagged finding list in this conversation — it converts that list
into escape rows instead of asking you to retype each one.

**Filter first — two thirds of a complexity list is usually not an escape:**

- Log ONLY findings against code this branch's coding loop produced and the
  review gates already blessed. Pre-existing debt that never went through the
  loop is not an escape; logging it inflates every gate ratio /audit review
  computes and there is no way to tell the two apart afterward.
- Skip anything already logged this branch by a structure or complexity finder
  — same file, same shape, one row.
- A list that ends in nothing to cut logs nothing. Say so and stop.

**Map each surviving finding:**

| Finding tag                                                                        | `class`      |
| ---------------------------------------------------------------------------------- | ------------ |
| dead code, speculative feature, one-implementation abstraction, config nobody sets | `complexity` |
| hand-rolled standard-library function, dependency doing what the platform ships    | `complexity` |
| same logic in fewer lines                                                          | `smell`      |

Fixed fields: `stage_found=refactor` (a post-hoc sweep of blessed code — the
same shape the structure sweep logs under, so the two stay one comparable
series; do not invent a new value) and `gate_missed=review`. `severity=low`
unless the finding removes a whole file or a live code path. One row per
distinct finding, not per file. Then run the ratchet once per `class` group per
its batching rule, and emit the step-3 command per row.

State the kept-vs-filtered count when you confirm — that ratio is the point of
the mode.

## Arguments

$ARGUMENTS
