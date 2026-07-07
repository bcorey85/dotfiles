# Shared Design-Decision Format (single source of truth)

The structure every recorded design decision follows, in both planning lanes
(`/q-plan` Phase D and `/eng-spec` Decisions). This is the artifact's
judgment surface — the part a human reads at the gate and `q-finalize`/`/adr`
distill later. Eval evidence (2026-07, `~/agent-evals/`): this block
structure plus the External Contracts rule below is where the decisive
invariant statements landed.

## Decision block (all four fields, every decision)

```markdown
### N. [Topic]

**Choice**: [what was decided]
**Reasoning**: [why — referencing user input where the user decided; tag the
owner: (User) for user-resolved, (Locked) for constraint-forced]
**Alternatives rejected**: [each considered option and why not]
**Trade-off accepted**: [what this choice makes worse, stated plainly]
```

- Never batch decisions into a table with one-line rationales — the
  Alternatives and Trade-off fields are where hollow choices get exposed.
- A decision with no real alternative is a constraint, not a decision —
  record it under Constraints instead.

## External Contracts rule (mandatory section in every design/spec)

Name every provider/API/platform contract the change touches and the
invariant it imposes (message-format pairing rules, identity/registry
semantics, rate limits, ordering guarantees) — and what breaks if violated.
**"None" must be stated explicitly, not implied by omission.** Internal
invariants discovered in research (identity construction, hidden couplings)
belong here too when the change's blast radius depends on them.
