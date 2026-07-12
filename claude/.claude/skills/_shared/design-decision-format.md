# Shared Design-Decision Format (fm-v5)

<!-- The `fm-vN` tag versions THIS text and is referenced by the planning-lane
eval records in `deep-plan/DESIGN.md`. Bump it when this file changes
materially and note the change in the eval program's next pre-registration.
fm-v5 (2026-07-11, amended 2026-07-12 before any real-work use): owner tags
split User → User-originated | User-ratified, paired with the framing pass
(`_shared/framing-pass.md`) and the ratification alarm in both lanes' phase
reviews. The alarm counts `(User-originated)` decisions and fires on ZERO of
them (an earlier draft asked "is every decision ratified", which one `(Locked)`
block silenced). This file is the SOLE statement of the owner tags and the
alarm: consumers reference §§ Owner tags / The ratification alarm and must not
restate the rules — every drift between copies has been a defect. Amended in
place rather than bumped to fm-v6 because fm-v5 never ran on a real ticket. -->

Single source of truth.

The structure every recorded design decision follows, in both planning lanes
(`/deep-plan` Phase D and `/eng-spec` Decisions). This is the artifact's
judgment surface — the part a human reads at the gate and `finalize`/`/adr`
distill later. This block structure plus the External Contracts rule below
is where decisive invariant statements tend to land.

## Decision block (all four fields, every decision)

```markdown
### N. [Topic]

**Choice**: [what was decided]
**Reasoning**: [why — referencing user input where the user decided; tag the
owner with exactly one of the three values below]
**Alternatives rejected**: [each considered option and why not — name the
concrete user-visible failure mode the alternative would cause, not only its
technical demerits; a rejection that names no failure mode is unsupported]
**Trade-off accepted**: [what this choice makes worse, stated plainly]
```

## Owner tags (exactly one per decision)

| Tag | Means | Test |
| --- | --- | --- |
| `(User-originated)` | **The user's judgment is visible in the outcome.** Any one of: they named this choice (or the direction it came from) in the framing pass; they picked an option that was NOT the agent's recommendation; or they materially edited what the agent proposed. | Did the user's input change the outcome from what the agent would have written alone? |
| `(User-ratified)` | The agent framed the choice, generated the options, ranked them, and the user took the top-ranked one unchanged. | The choice IS the agent's recommendation, and nothing material was added or altered. |
| `(Locked)` | A real fork existed, and a constraint killed every option but one. | Name the constraint AND the option it killed. If you can't name a killed option, no fork ever existed — that is not a decision, it is a constraint. Write no block; record it under Constraints. |

The tags key on **whose judgment shaped the outcome**, not on which phase the
decision happened in. Decisions surface late — an architect's finalization or a
planner's detail work can force a real choice after the design conversation has
closed (the `DESIGN GAPS` protocol). Route it back to the user and tag it by
these same tests. There is deliberately no "decided after the gate" tag: a
decision with nobody's name on it is what this scheme exists to make impossible.

**When two tags could fit, resolve in this order.** The enumerated cases serve
these two questions; they are not a closed list to pattern-match against.

1. **What actually decided this?** If a constraint killed every option but one,
   it is `(Locked)` — even if you put it to the user as a question and they
   agreed. They could not have answered otherwise, and recording their
   acknowledgment as a choice credits them with judgment they never exercised.
   (Asking anyway is fine and often right. Just don't score it.)
2. **Did the user's input change the outcome from what you'd have written
   alone?** Yes → `(User-originated)`. That is the question the alarm counts.

So: taking your second-ranked option is `(User-originated)` — they overrode your
ranking. So is the negotiation shape, where they reject your recommendation, you
go find something else, and they take it: you wrote the words, but their pushback
is why that option exists. Unless what you came back with was the only thing a
constraint had left standing — then step 1 already decided it, and it is
`(Locked)`.

`(User)` is not a valid tag. It collapsed origination and ratification into one
value, so a user who accepted every recommendation and a user who designed the
thing produced identical artifacts.

## The ratification alarm

**Single source of truth. Consumers reference this section; they do not restate
the threshold — every past drift between copies has been a defect.**

`(User-ratified)` is a legitimate tag, not a failure. Accepting a good
recommendation is fine, and on routine work most decisions will be ratified. The
finding is at the aggregate, and it is a floor on the user's judgment, not a
ceiling on the agent's. It fires in exactly two forms:

> **Zero-originated** — the artifact records more than one decision and NONE is
> `(User-originated)`. Nothing the user said changed any outcome. Count
> originations; do NOT ask "is every decision ratified" — one `(Locked)` block
> would silence that, and `(Locked)` means a constraint decided it, never that
> the user did. An all-`(Locked)` artifact is zero-originated and fires.
>
> **Zero-decision** — the artifact records no decision blocks at all, because a
> lane declared there was nothing to decide. The user was never shown a choice.
> Louder version of the same signal, not an exempt case.
>
> A single non-originated decision is not a pattern. It does not fire.

Canonical report lines — surface one, verbatim, in the user's own next message:

> Ratification alarm: none of the N decisions here were yours. I framed them,
> proposed them (or a constraint forced them), and none traced back to your
> framing. Worth a look before we build on it.

> Ratification alarm: this records no decisions at all. You were never shown a
> choice. Worth confirming there really was nothing to decide.

"The recommendations were right" and "there was nothing to decide" are both fine
answers, and the alarm has still done its job. What it prevents is the case where
nobody noticed.

**It is the one finding that may never be fixed.** The only way to "fix" it is to
re-tag decisions, which manufactures the exact false audit trail the tags exist to
expose. Report it, log it, carry it to the user. Never revise, never block.
Automation bias is documented to occur in experts and to survive instructions to
verify (Parasuraman & Manzey 2010), so "I read it carefully" is not a defense the
artifact can rely on — the count is the control. The signal is longitudinal: a run
of zero-originated artifacts in the review log is the thing to look at, not any
single one.

## Rules

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
