# Shared Design-Decision Format

The structure every recorded design decision follows (`/eng-spec` `## Decisions`) — the judgment surface humans gate on and `/adr` distills.


## Decision block (all four fields, every decision)

```markdown
### N. [Topic]

**Choice**: [what was decided]
**Reasoning**: [why — reference the user's input where the user decided]
**Alternatives rejected**: [each considered option and why not — name the
concrete user-visible failure mode the alternative would cause, not only its
technical demerits; a rejection that names no failure mode is unsupported]
**Trade-off accepted**: [what this choice makes worse, stated plainly]
```

## Rules

- Never batch decisions into a table with one-line rationales — the Alternatives
  and Trade-off fields are where hollow choices get exposed.
- The failure-mode requirement forces the invariant open: adjacent-only justification leaves the real constraint unstated.
- **No real alternative = constraint, not decision** — record under Constraints. Can't name a killed option → no fork existed.
- **Split the check out of the decision.** A claim shaped like _"we know X because we looked at Y"_ is its own decision with its own block.
- **Credentials past user intent — never default.** A decision leaving secrets/data alive past explicit removal intent must state that consequence in security terms and requires explicit user sign-off.
- **Scope-only rejections require explicit user sign-off — never a default. Scope is the ticket-owner's call.**

## External Contracts rule (mandatory section in every spec)

Name every touched provider/API/platform contract + invariant + what breaks if violated. **"None" stated explicitly, never implied.** Blast-radius internal invariants (identity construction, hidden couplings) too.

**Runtime-acceptance evidence rule.** When the change alters what an external tool ACCEPTS/ENFORCES at runtime, each acceptance claim states its evidence class:

- **exercised** — upstream citation for the exact runtime path, or a plan step exercising the real tool pre-rollout; OR
- **declared-only** — schema text, types, vendored docs, comments, in-repo precedent (intent, not behavior). Accepted-by-the-tool claims may NOT rest on declared-only: upgrade the evidence or add the staged step, and say which.
