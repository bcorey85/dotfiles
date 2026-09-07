# ADR Template & Discipline (shared)

Single source of truth for decision-record output. Consumed by `/adr`. The consuming skill supplies the SOURCES for each section; everything here — structure, caps, discipline — applies verbatim.

## Who this is written for

The reader **two years out** — human or agent — deciding whether this still holds.

## Section rubric

Eight sections, in order. A fact fitting nowhere belongs in eng-arch or code.

| Section               | Purpose                                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Header                | Status / Supersedes / Ticket / PR / Date / Reversibility — stacked bullets                                           |
| TL;DR                 | ≤3 sentences (what/why/the one decision). Never introduces facts absent from the body. **Written last**              |
| Problem               | 1–2 paras, technical only (strip story framing)                                                                      |
| Decision              | 1–2 paras, what we built                                                                                             |
| Alternatives rejected | One option not taken + 1–3 sentences why                                                                             |
| Assumptions           | The conditions the decision depends on, each stated so it can be **checked later** ("valid while …", "revisit if …") |
| Watch out for         | Limits in one list: risks, drift, coupling, deliberate non-goals, uncovered anti-patterns. No manufactured downsides |
| Addenda               | Dated, append-only outcome trail. Omit at creation; the first addendum adds the section                              |
| Related               | Eng-arch links — only if eng-arch was updated; else omit                                                             |

**Three sections cut deliberately — do not reintroduce**: `Consequences` (restated Decision; outcomes → dated `Addenda`), `Patterns` (state-of-code rots; cross-link eng-arch), `Constraints` (indistinguishable from `Watch out for`).

## Discipline

- **Status**: `Accepted` default. `Deprecated` when no longer in force. `Superseded by IQ-YYY` (with link) when replaced — and the replacement carries `Supersedes: IQ-XXX`, so the chain reads in both directions.
- **Body freezes at Accepted; header doesn't.** `Status`/`Supersedes`/`PR` stay mutable bookkeeping.
- **Two legal post-Accepted body mutations**: 1. **Addendum** (dated line under `## Addenda`; never alters above). 2. **Supersession** (NEW record; flip `Status` here, leave body). Silent edits destroy the audit chain.
- **Addendum format** — one line, ISO date, newest last (append-only): `- **YYYY-MM-DD** — [what happened]`. Tag the kind inline when it has one: `assumption broken:`, `escape IQ-XXX:`, `outcome:`.
- **Assumptions are testable or filler** — "valid while single-region" beats "reasonable scale".
- **Reversibility is one line**: `two-way door` (cheap to undo) or `one-way door` (migration, published API, data model) plus one clause on why.
- **No manufactured downsides**: trust `Alternatives rejected` to carry the trade-off load.
- **Unmeasured wins → dated `Addenda`, not the body.** Measured numbers belong in Problem/Decision as evidence.

## Write for skimmability

Apply `~/.claude/skills/_shared/skimmable-writing.md` in full, plus:

- **One Diátaxis mode**: ADRs are **explanation** — no state-of-code reference (eng-arch's job); cross-link.
- **Headings = answers**, ADR flavor: a heading names the finding (`Status: Accepted`, `FormData Content-Type footgun`) rather than the slot it sits in (`Status field`, `Implementation note 3`).
- **Per-section line caps** (hard — if you blow it, you're writing the wrong section): TL;DR ≤ 3 sentences. Problem ≤ 8. Decision ≤ 8. Alternatives ≤ 12. Assumptions ≤ 6. Watch out for ≤ 10.
- **Target 50–80 lines** at creation (Addenda exempt). Past that, you're writing eng-arch material (Mega-ADR).

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
