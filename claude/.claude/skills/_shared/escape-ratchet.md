# Escape Ratchet (one guard per escape)

The guard decision every `log-escape` call carries. Read before logging.

Consumers: `/escape`, `/cc`, `/fix`, `/refactor`, `/verify-branch`,
`/commit`, `/audit review`.

## The decision

Per escape: _cheapest structural guard that would have caught it?_ First applicable rung:

1. **`type`** — type / lint / schema change that makes the illegal state
   unrepresentable (e.g. token union turns `xxs` vs `2xs` into a compile error).
2. **`convention`** — one line where coders/reviewers already look (project CLAUDE.md).
3. **`gotcha`** — one dated line in the owning SKILL.md's `## Gotchas` (create if absent); for workflow defects, not code conventions.
4. **`rule`** — a calibration line in the relevant agent file. Weakest rung —
   use only when 1–3 are impossible.

**Plan-stage escapes take a different rung** (code matched spec; no reviewer could catch): rungs 1–4 mostly don't apply. Take:

5. **`check`** — one command where finalization already runs commands: a falsification-sweep line. FIRST rung for plan-stage, before `none`.

`none` is legal for one-offs — but a decision, not a default: reach it only after rejecting 1–4.

Propose the guard; on approval apply it (or ticket it for another repo). Pass the rung as `guard=` — the script rejects lines without one.

## Miss reason

Every `log-escape` call also carries `miss_reason=`, why the gate missed this defect. First label that fits:

1. **`plan-gap`** — the plan was wrong or silent, and the code matched it.
2. **`out-of-scope`** — the defect sits in code the reviewed diff did not change.
3. **`seen-dismissed`** — a reviewer raised it and it was dropped.
4. **`needs-runtime`** — it shows only when the code runs.
5. **`needs-other-file`** — seeing it needs a file outside the diff, such as an existing helper or owner.
6. **`rule-absent`** — it is visible in the diff and no rule told a reviewer to flag it.
7. **`overlooked`** — it is visible in the diff, a rule covers it, and nobody flagged it.

`unknown` is for scripts. A model caller picks a label.

## Batching

Several escapes one pass → group by `class`, ONE guard per group. Every row still carries a `guard` value and its own `miss_reason`.

## ADR addendum

Defect tracing to an ADR decision → also append a dated `## Addenda` line (never touch sections above).
