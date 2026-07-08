# Shared Design-Decision Format (single source of truth)

The structure every recorded design decision follows, in both planning lanes
(`/q-plan` Phase D and `/eng-spec` Decisions). This is the artifact's
judgment surface — the part a human reads at the gate and `q-finalize`/`/adr`
distill later. This block structure plus the External Contracts rule below
is where decisive invariant statements tend to land.

## Decision block (all four fields, every decision)

```markdown
### N. [Topic]

**Choice**: [what was decided]
**Reasoning**: [why — referencing user input where the user decided; tag the
owner: (User) for user-resolved, (Locked) for constraint-forced]
**Alternatives rejected**: [each considered option and why not — name the
concrete user-visible failure mode the alternative would cause, not only its
technical demerits; a rejection that names no failure mode is unsupported]
**Trade-off accepted**: [what this choice makes worse, stated plainly]
```

- Never batch decisions into a table with one-line rationales — the
  Alternatives and Trade-off fields are where hollow choices get exposed.
- The failure-mode requirement is what forces the invariant into the open: a
  correct choice justified only by adjacent reasons (portability, reuse,
  reboot-survival) leaves the real constraint unstated, and the next reader
  "simplifies" back to the rejected option.
- **Credentials past user intent — never default this.** When a decision's
  chosen behavior or accepted trade-off leaves credentials, secrets, or user
  data alive past a user's explicit removal/revocation/disconnect intent,
  the block must state that consequence in security terms ("after the user
  asks to disconnect, X remains on disk / remains usable"), and the decision
  must be marked as requiring explicit user sign-off — it may not be
  resolved by a default or by accepting a recommended option. The security
  framing is what the human at the gate needs to weigh retention against
  hygiene; a scope-argument framing hides the stakes.
- **Scope-only rejections require the user's answer (engaged gate).** When
  an alternative is rejected SOLELY on scope grounds ("not requested",
  "out of ticket scope", "scope creep") rather than on a technical failure
  mode, the decision must be marked as a judgment call requiring explicit
  user sign-off — it may not be resolved by a default or by accepting the
  recommended option on the user's behalf. Rationale (plan-ab rounds 7 and
  11): both lanes reliably SURFACE the correct alternative and then decline
  it on scope discipline; twice that reproduced the exact regression the
  maintainer shipped and reverted. Scope is the ticket-owner's call, not
  the artifact's.
- A decision with no real alternative is a constraint, not a decision —
  record it under Constraints instead.

## External Contracts rule (mandatory section in every design/spec)

Name every provider/API/platform contract the change touches and the
invariant it imposes (message-format pairing rules, identity/registry
semantics, rate limits, ordering guarantees) — and what breaks if violated.
**"None" must be stated explicitly, not implied by omission.** Internal
invariants discovered in research (identity construction, hidden couplings)
belong here too when the change's blast radius depends on them.

**Runtime-acceptance evidence rule.** When the change alters what an
external tool ACCEPTS or ENFORCES at runtime — a verifier, policy engine,
admission controller, parser, migration runner, or any component that can
reject or ignore configuration/input it is handed — each contract claim
about what that tool accepts must state its evidence class:

- **exercised** — an upstream doc/issue/source citation for the exact
  runtime path, or a dry-run/staged step in the plan that exercises the
  real tool before rollout; OR
- **declared-only** — schema text, type shapes, vendored docs, comments,
  or in-repo precedent. Declared-only evidence describes intent, not
  behavior, and a precedent may exercise a different path. A design may
  NOT rest an accepted-by-the-tool claim on declared-only evidence: it
  must either upgrade the evidence or add the staged exercise step, and
  say which.
