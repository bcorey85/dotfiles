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
