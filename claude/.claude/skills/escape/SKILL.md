---
name: escape
description: Log a defect that escaped the automated loop — caught by human PR reading, in production, or anywhere downstream of the gates. Appends to `~/.claude/review-escapes.jsonl`, the ground-truth side of the review flywheel (aggregated by /audit review). Triggers on "log escape", "the loop missed this", "this got past review", "/escape".
allowed-tools: [Bash, Read, Glob, Grep, Edit]
---

# Log an Escape

One escape = one defect found downstream of the gate that should have caught it. `/cc`, `/fix` (conversation-sourced findings, as `stage_found=walkthrough`), `/refactor`, and `/verify` log their own escapes automatically; this skill is the manual channel for everything else — things you catch reading a PR, a prod bug traced back to loop output, a smell noticed weeks later.

## Instructions

1. **Extract the fields** from `$ARGUMENTS` and the conversation:
   - `stage_found` — where the defect surfaced: `walkthrough` (you, reading `/stage`'s queue at a phase sign-off — inside the loop), `pr-human` (you, reading the diff after it left the gates), `prod`, `verify`, `other`
   - `gate_missed` — which layer should have caught it: `review` (bugs/quality), `drift-gate` (plan drift), `test-intent` (bug-pinning tests), `stage` (bug in a mechanically-staged SAFE-tier file — the invariant failed), `coder` (should never have been written)
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

## Arguments

$ARGUMENTS
