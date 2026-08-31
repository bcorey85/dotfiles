# ADR Template & Discipline (shared)

Single source of truth for decision-record output. Consumed by `/adr`. The consuming skill supplies the SOURCES for each section; everything here — structure, caps, discipline — applies verbatim.

## Who this is written for

Not the author, and not this month's reviewer: the reader **two years out** — human or agent — who has to change, challenge, or build on this decision and needs to know whether it still holds. Every section rule below serves that reader.

## Section rubric

Eight sections, in this order. There is no ninth: a fact that fits nowhere here belongs in eng-arch or in the code.

| Section               | Purpose                                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Header                | Status / Supersedes / Ticket / PR / Date / Reversibility — stacked bullets                                                                                                                                              |
| TL;DR                 | ≤3 sentences: what changed, why, the one decision a future reader must know. **Written last**, never introduces facts absent from the body. Doubles as peer-review orientation and the retrieval chunk agents see first |
| Problem               | 1–2 paras, technical only (strip story framing)                                                                                                                                                                         |
| Decision              | 1–2 paras, what we built                                                                                                                                                                                                |
| Alternatives rejected | Load-bearing, and placed high because it answers the returning reader's first question — has someone already tried the thing I am about to propose? One option not taken + 1–3 sentences why                            |
| Assumptions           | The conditions the decision depends on, each stated so it can be **checked later** ("valid while …", "revisit if …"). This is what makes staleness detectable instead of discovered                                     |
| Watch out for         | Every limit on the decision in one list: risks accepted, drift, hidden coupling, what the code deliberately does NOT do, and any anti-pattern the work uncovered. Do NOT manufacture downsides                          |
| Addenda               | Dated, append-only outcome trail. Omit at creation; the first addendum adds the section                                                                                                                                 |
| Related               | Eng-arch links — only if eng-arch was updated; else omit                                                                                                                                                                |

**Three sections were cut deliberately; do not reintroduce them.** `Consequences → Easier` restated Decision as benefits, and a real outcome is not known at creation time anyway — it belongs in `Addenda`, dated, once someone has measured it. `Patterns → To follow` is state-of-code reference sitting inside an explanation document, and it rots the first time a line is added above the one it cites; cross-link eng-arch instead. `Constraints` was never reliably distinguishable from `Watch out for`, so the two are now one list.

## Discipline

- **Status**: `Accepted` default. `Deprecated` when no longer in force. `Superseded by IQ-YYY` (with link) when replaced — and the replacement carries `Supersedes: IQ-XXX`, so the chain reads in both directions.
- **The body freezes at Accepted; the header does not.** Everything from `## TL;DR` down is frozen. The header bullets are mutable metadata — `Status`, `Supersedes`, and `PR` get filled in or flipped as the record's world changes (`PR` is `(pending)` at creation, since `/adr` runs before the PR opens). Changing a header bullet is bookkeeping, not a rewrite of the decision.
- **Two legal mutations to the body after Accepted, nothing else**:
  1. **Addendum** — a dated line appended under `## Addenda`: outcomes, escapes traced back to this decision, an assumption observed broken. Never alters anything above it.
  2. **Supersession** — a changed decision gets a NEW record that supersedes this one. Flip this record's `Status` to `Superseded by IQ-YYY` (header bookkeeping, per above) and leave the body untouched.
     Silent edits destroy the audit chain; the trail is only trustworthy if readers can rely on Accepted body text being frozen.
- **Addendum format** — one line, ISO date, newest last (append-only): `- **YYYY-MM-DD** — [what happened]`. Tag the kind inline when it has one: `assumption broken:`, `escape IQ-XXX:`, `outcome:`.
- **Assumptions are testable or they're filler**: "we assume reasonable scale" records nothing; "valid while single-region" can be checked in 30 seconds by the reader who wonders if this still applies.
- **Reversibility is one line**: `two-way door` (cheap to undo) or `one-way door` (migration, published API, data model) plus one clause on why. Tells the future reader how much evidence they need before re-litigating.
- **No manufactured downsides**: trust `Alternatives rejected` to carry the trade-off load. Thin filler is worse than asymmetry.
- **Claimed wins go in `Addenda`, not the body.** "This made X faster" written on the day of the change is a prediction wearing a result's clothes. If it was measured, the number belongs in Problem or Decision as evidence; if it was not, wait and add a dated addendum.

## Write for skimmability

Read `~/.claude/skills/_shared/skimmable-writing.md` (single source of truth for the skimmability rules) and apply it in full. ADR-specific additions:

- **One Diátaxis mode**: ADRs are **explanation** (_why_ we decided). Do NOT mix in state-of-code reference — that's eng-arch's job. Cross-link instead.
- **Headings = answers**, ADR flavor: a heading names the finding (`Status: Accepted`, `FormData Content-Type footgun`) rather than the slot it sits in (`Status field`, `Implementation note 3`).
- **Per-section line caps** (hard — if you blow it, you're writing the wrong section): TL;DR ≤ 3 sentences. Problem ≤ 8. Decision ≤ 8. Alternatives ≤ 12. Assumptions ≤ 6. Watch out for ≤ 10.
- **Target 50–80 lines** at creation (Addenda growth is exempt — it's append-only history). Past that, you're including state-of-code material that belongs in eng-arch (Mega-ADR anti-pattern).

## Template

```markdown
# IQ-XXX: [Feature name from ticket]

- **Status**: Accepted
- **Supersedes**: [IQ-YYY](link) — omit if none
- **Ticket**: [IQ-XXX](jira-url) — from `**URL:**` in the ticket; if no URL is recorded, use the key as plain text (do NOT invent a tracker URL)
- **PR**: `(pending)` — normal at creation; becomes [repo#NNN](pr-url) once the PR opens
- **Date**: YYYY-MM-DD
- **Reversibility**: two-way door — [one clause] | one-way door — [one clause]

## TL;DR

[≤3 sentences. Written last.]

## Problem

[1–2 paras]

## Decision

[1–2 paras]

## Alternatives rejected

- **[Option]** — [why not, 1–3 sentences]

## Assumptions

- [Checkable condition: "valid while …" / "revisit if …"]

## Watch out for

- [Latent risk, drift, hidden coupling, deliberate non-goal, or an anti-pattern this work uncovered]

<!-- ## Addenda — OMIT at creation. The first addendum adds the section. Append-only, newest last:
- **YYYY-MM-DD** — outcome: [what happened]
- **YYYY-MM-DD** — assumption broken: [which one, what changed]
- **YYYY-MM-DD** — escape IQ-XXX: [defect traced back to this decision]
-->

## Related

[Omit unless eng-arch updated]

- Eng-arch: `docs/architecture/[subsystem].md`
```
