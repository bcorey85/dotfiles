# Escape Ratchet (one guard per escape)

Single source of truth for the guard decision every `log-escape` call carries.
Read this before logging an escape to the review flywheel.

Consumers: `/escape`, `/cc`, `/fix`, `/refactor`, `/verify`,
`/commit`, `/audit review`.

## The decision

For each escape, ask: _what is the CHEAPEST structural guard that would have
caught this at the gate it escaped?_ Work down this hierarchy and stop at the
first rung that applies:

1. **`type`** — type / lint / schema change that makes the illegal state
   unrepresentable (e.g. a design-token union type turns `xxs` vs `2xs` into a
   compile error). Always prefer this rung.
2. **`convention`** — one line in the project's CLAUDE.md or conventions doc,
   where coders and reviewers already look.
3. **`gotcha`** — when the defect traces to a workflow a skill owns (not a code
   convention), one dated line appended to that SKILL.md's `## Gotchas` section
   (create it if absent).
4. **`rule`** — a calibration line in the relevant agent file. Weakest rung: it
   spends prompt budget forever and relies on recall. Use only when 1–3 are
   impossible.

**Plan-stage escapes take a different rung.** When the defect was in the plan —
the code matched the spec exactly and no reviewer could have caught it — rungs
1–4 mostly do not apply: there is no illegal state to type out, and a convention
does not stop a spec from asserting a stale count. Take:

5. **`check`** — one command added where finalization already runs commands: a
   line in the spec finalization phase's falsification sweep, or a rule in
   `~/.claude/scripts/spec-criteria-lint.sh` when the shape is mechanically
   detectable. Prefer the lint when the defect is a pattern in the plan's text
   (a path, a token, a target); prefer the sweep when it needs the tree to
   answer (a count, a flag's real behavior, a deliverable that already landed).
   This is the FIRST rung to try for a plan-stage escape, before considering
   `none` — a plan defect that closes nothing recurs in the next spec, because
   nothing about the next spec's authoring changed.

`none` is a legal outcome — a one-off not worth guarding. It is a decision, not
a default: reach it only after 1–4 have been considered and rejected.

Propose the specific guard to the user; on approval, apply it (or create a
ticket if it belongs in another repo). Then pass the chosen rung as
`guard=type|convention|gotcha|rule|none` on the `log-escape` line. The script
rejects a line without it.

## Batching

When one pass produces several escapes (a `/refactor` sweep, a `/verify` gap
list), group them by `class` and propose ONE guard per group — a recurring
pattern gets one guard, not N copies. Every logged row still carries a `guard`
value: the group's rung, or `none`.

## ADR addendum

If the defect traces back to a decision recorded in an ADR
(`docs/decisions/*.md`), also append a dated line to that ADR's `## Addenda`
section (create the section if absent) — one of the two legal mutations
`_shared/adr-template.md` allows. Never edit the sections above it.
