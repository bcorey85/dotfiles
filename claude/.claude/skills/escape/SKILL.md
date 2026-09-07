---
name: escape
description: Log a defect that escaped the automated loop — caught by human PR reading, in production, or anywhere downstream of the gates. Appends to `~/.claude/review-escapes.jsonl`, the ground-truth side of the review flywheel (aggregated by /audit review). Triggers on "log escape", "the loop missed this", "this got past review", "/escape", and "log these over-engineering findings".
allowed-tools: [Bash, Read, Glob, Grep, Edit]
---

# Log an Escape

One escape = one defect found downstream of its gate. `/cc`/`/fix`/`/refactor`/`/verify` log their own automatically; this is the manual channel for everything else (PR reads, prod bugs, late-noticed smells).

## Instructions

1. **Extract the fields** from `$ARGUMENTS` and the conversation:
   - `stage_found` — where it surfaced: `walkthrough` (you, at phase sign-off), `phase-gate` (downstream agent, in-loop), `pr-human` (you, post-gates), `prod`, `verify`, `other`
   - `gate_missed` — which layer should have caught it: `review` (bugs/quality), `drift-gate` (plan drift), `test-intent` (bug-pinning), `stage` (SAFE-tier invariant failed), `coder` (should never have been written), `eng-spec` (**defect was in the plan** — use whenever implementation faithfully matched a wrong spec, never `coder`).
   - `class` — `bug` | `smell` | `duplication` | `complexity` | `plan-drift` | `test-gap` | `other` (`complexity` = code that need not have existed, the `/refactor simplify` class)
   - `severity` — `high` | `medium` | `low`
   - `desc` — one line, specific enough to be legible in 3 months
   - `file` — representative path, if known
   - `lane` — optional planning lane (`eng-spec`/`code`/`other`); ask when ambiguous.

   If the description is too vague to classify, ask ONE clarifying question. A new requirement or changed mind is NOT an escape.

2. **Ratchet** — run the guard decision per `~/.claude/skills/_shared/escape-ratchet.md` (including its ADR addendum) and carry the chosen rung into the log line below.

3. **Log it**:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")" stage_found=<...> gate_missed=<...> class=<...> severity=<...> lane=<...> guard=<...> desc="<...>" file=<...>
   ```

4. **Confirm** by echoing the logged fields plus guard, then stop. Never fixes — route through `/fix`.

## Batch mode: an over-engineering review's finding list

Triggered by `/escape ponytail` (or any complexity-review finding list in this conversation) — converts the list into escape rows.

**Filter first:**

- Log ONLY branch-loop-produced, gate-blessed code. Pre-existing debt is not an escape.
- Skip anything already logged this branch by a structure or complexity finder
  — same file, same shape, one row.
- A list that ends in nothing to cut logs nothing. Say so and stop.

**Map each surviving finding:**

| Finding tag | `class` |
| --- | --- |
| dead code, speculative feature, one-implementation abstraction, config nobody sets | `complexity` |
| hand-rolled standard-library function, dependency doing what the platform ships | `complexity` |
| same logic in fewer lines | `smell` |

Fixed fields: `stage_found=refactor` (same shape as the structure sweep — one comparable series, never a new value) and `gate_missed=review`. `severity=low` (unless removing a file/live path). One row per distinct finding, not per file. Ratchet once per `class` group, step-3 command per row.

State the kept-vs-filtered count when you confirm.

## Arguments

$ARGUMENTS
