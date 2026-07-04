---
name: escape
description: Log a defect that escaped the automated loop — caught by human PR reading, in production, or anywhere downstream of the gates. Appends to `~/.claude/review-escapes.jsonl`, the ground-truth side of the review flywheel (aggregated by /review-stats). Triggers on "log escape", "the loop missed this", "this got past review", "/escape".
allowed-tools: [Bash, Read, Glob, Grep, Edit]
---

# Log an Escape

One escape = one defect found downstream of the gate that should have caught it. `/cc`, `/refactor`, and `/q-verify` log their own escapes automatically; this skill is the manual channel for everything else — things you catch reading a PR, a prod bug traced back to loop output, a smell noticed weeks later.

## Instructions

1. **Extract the fields** from `$ARGUMENTS` and the conversation:
   - `stage_found` — where the defect surfaced: `pr-human` (you, reading the diff), `prod`, `verify`, `other`
   - `gate_missed` — which layer should have caught it: `review` (bugs/quality), `drift-gate` (plan drift), `test-intent` (bug-pinning tests), `coder` (should never have been written)
   - `class` — `bug` | `smell` | `duplication` | `plan-drift` | `test-gap` | `other`
   - `severity` — `high` | `medium` | `low`
   - `desc` — one line, specific enough to be legible in 3 months
   - `file` — representative path, if known

   If the description is too vague to classify, ask ONE clarifying question — a mislabeled escape pollutes the very data this exists to produce. A new requirement or changed mind is NOT an escape; only log things a gate should have caught with the information it had.

2. **Log it**:

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")" stage_found=<...> gate_missed=<...> class=<...> severity=<...> desc="<...>" file=<...>
   ```

3. **Ratchet — one guard per escape (the actual loop-closer).** Recording the miss is bookkeeping; preventing the recurrence is the point. Ask: _what is the CHEAPEST structural guard that would have caught this at the gate it escaped?_ Work down this hierarchy and stop at the first rung that applies:

   1. **Type / lint / schema** — make the illegal state unrepresentable (e.g. a design-token union type turns `xxs` vs `2xs` into a compile error). Caught by the execution gate forever, at zero attention cost. Always prefer this rung.
   2. **Stated convention** — one line in the project's CLAUDE.md or conventions doc, where coders and reviewers already look. Conventions that live only in humans' heads are invisible to every gate.
   3. **Skill gotcha** — when the defect traces to a workflow a skill owns (not a code convention), append one dated line to that SKILL.md's `## Gotchas` section (create it if absent). Gotchas built from observed failures are the highest-signal content a skill carries — this rung is how the toolkit itself learns.
   4. **Agent/reviewer rule** — a calibration line in the relevant agent file. Weakest rung: it spends prompt budget forever and relies on recall. Use only when 1–3 are impossible.

   Propose the specific guard to the user; on approval, apply it (or create a ticket if it belongs in another repo). Then append `guard=type|convention|gotcha|rule|none` to the log line so `/review-stats` can flag escapes that never got a guard.

   **ADR addendum**: if the defect traces back to a decision recorded in an ADR (`docs/eng-specs/*.md`), also append a dated line to that ADR's `## Addenda` section (create the section if absent) — outcomes are part of the record, and this is one of the two legal mutations `_shared/adr-template.md` allows. Never edit the sections above it.

4. **Confirm** by echoing the logged fields and the guard decision, then stop. This skill never fixes the defect itself — route fixes through `/fix`.

## Arguments

$ARGUMENTS
