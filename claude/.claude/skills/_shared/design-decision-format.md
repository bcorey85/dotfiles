# Shared Design-Decision Format

Single source of truth. The structure every recorded design decision follows, in
`/eng-spec`'s `## Decisions`. This is the artifact's judgment surface — the part
a human reads at the gate and `/adr` distills later. This block structure plus
the External Contracts rule below is where decisive invariant statements tend to
land.

<!-- History: this file previously carried owner tags (User-originated /
User-ratified / Locked) and a "ratification alarm" that fired when no decision
traced back to the user. Both were removed 2026-07-13. They worked exactly as
designed — the alarm fired correctly on the most truthful artifact the system
ever produced, which was still wrong. They were a prosthetic for the user's
absence from the design phase, and you cannot tag your way to having been
present. Do not reintroduce them; the fix is that the user is in the room, which
is what /eng-spec Phase 5 is for. -->

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
- The failure-mode requirement is what forces the invariant into the open: a
  correct choice justified only by adjacent reasons (portability, reuse,
  reboot-survival) leaves the real constraint unstated, and the next reader
  "simplifies" back to the rejected option.
- **A decision with no real alternative is a constraint, not a decision** —
  record it under Constraints instead. If you cannot name an option that a
  constraint killed, no fork ever existed.
- **Split the check out of the decision.** When a decision contains a claim
  shaped like *"we know X because we looked at Y"* — does this record exist? is
  this the same user? is this process still alive? is this value unique? — that
  check is its own decision and gets its own block. Every regression this system
  has shipped lost it as a subordinate clause inside a decision about something
  else.
- **Credentials past user intent — never default this.** When a decision's chosen
  behavior or accepted trade-off leaves credentials, secrets, or user data alive
  past a user's explicit removal/revocation/disconnect intent, the block must
  state that consequence in security terms ("after the user asks to disconnect, X
  remains on disk / remains usable"), and the decision requires explicit user
  sign-off — it may not be resolved by a default or by accepting a recommended
  option. The security framing is what the human at the gate needs in order to
  weigh retention against hygiene; a scope-argument framing hides the stakes.
- **Scope-only rejections require the user's answer.** When an alternative is
  rejected SOLELY on scope grounds ("not requested", "out of ticket scope",
  "scope creep") rather than on a technical failure mode, the decision requires
  explicit user sign-off — it may not be resolved by a default or by accepting
  the recommendation on the user's behalf. Rationale: in the eval program both
  lanes reliably SURFACED the correct alternative and then declined it on scope
  discipline; twice that reproduced the exact regression the maintainer shipped
  and reverted. **Scope is the ticket-owner's call, not the artifact's.**

## External Contracts rule (mandatory section in every spec)

Name every provider/API/platform contract the change touches and the invariant it
imposes (message-format pairing rules, identity/registry semantics, rate limits,
ordering guarantees) — and what breaks if violated. **"None" must be stated
explicitly, not implied by omission.** Internal invariants discovered in research
(identity construction, hidden couplings) belong here too when the change's blast
radius depends on them.

**Runtime-acceptance evidence rule.** When the change alters what an external tool
ACCEPTS or ENFORCES at runtime — a verifier, policy engine, admission controller,
parser, migration runner, or any component that can reject or ignore
configuration/input it is handed — each contract claim about what that tool
accepts must state its evidence class:

- **exercised** — an upstream doc/issue/source citation for the exact runtime
  path, or a dry-run/staged step in the plan that exercises the real tool before
  rollout; OR
- **declared-only** — schema text, type shapes, vendored docs, comments, or
  in-repo precedent. Declared-only evidence describes intent, not behavior, and a
  precedent may exercise a different path. A design may NOT rest an
  accepted-by-the-tool claim on declared-only evidence: it must either upgrade the
  evidence or add the staged exercise step, and say which.
