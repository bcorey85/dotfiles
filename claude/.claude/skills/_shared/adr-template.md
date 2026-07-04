# ADR Template & Discipline (shared)

Single source of truth for decision-record output. Consumed by `/q-finalize` (QRSPI lane) and `/adr` (eng-spec and small-feature lanes). The consuming skill supplies the SOURCES for each section; everything here — structure, caps, discipline — applies verbatim.

## Who this is written for

Not the author, and not this month's reviewer: the reader **two years out** — human or agent — who has to change, challenge, or build on this decision and needs to know whether it still holds. Every section rule below serves that reader.

## Section rubric

| Section               | Purpose                                                                                                                                                                                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Header                | Status / Supersedes / Ticket / PR / Date / Reversibility — stacked bullets                                                                                                                                              |
| TL;DR                 | ≤3 sentences: what changed, why, the one decision a future reader must know. **Written last**, never introduces facts absent from the body. Doubles as peer-review orientation and the retrieval chunk agents see first |
| Problem               | 1–2 paras, technical only (strip story framing)                                                                                                                                                                         |
| Decision              | 1–2 paras, what we built                                                                                                                                                                                                |
| Assumptions           | The conditions the decision depends on, each stated so it can be **checked later** ("valid while …", "revisit if …"). This is what makes staleness detectable instead of discovered                                     |
| Consequences          | `Easier` + `Watch out for`. Do NOT manufacture downsides                                                                                                                                                                |
| Alternatives rejected | Load-bearing. One option not taken + 1–3 sentences why                                                                                                                                                                  |
| Patterns              | To follow / To avoid — `path:line` refs, minimal prose                                                                                                                                                                  |
| Constraints           | Limits of approach, what code intentionally does NOT do                                                                                                                                                                 |
| Addenda               | Dated, append-only outcome trail. Omit at creation; the first addendum adds the section                                                                                                                                 |
| Related               | Eng-arch links — only if eng-arch was updated; else omit                                                                                                                                                                |

## Discipline

- **Status**: `Accepted` default. `Deprecated` when no longer in force. `Superseded by IQ-YYY` (with link) when replaced — and the replacement carries `Supersedes: IQ-XXX`, so the chain reads in both directions.
- **Two legal mutations after Accepted, nothing else**:
  1. **Addendum** — a dated line appended under `## Addenda`: outcomes, escapes traced back to this decision, an assumption observed broken. Never alters anything above it.
  2. **Supersession** — a changed decision gets a NEW record that supersedes this one.
     Silent edits destroy the audit chain; the trail is only trustworthy if readers can rely on Accepted text being frozen.
- **Assumptions are testable or they're filler**: "we assume reasonable scale" records nothing; "valid while single-region" can be checked in 30 seconds by the reader who wonders if this still applies.
- **Reversibility is one line**: `two-way door` (cheap to undo) or `one-way door` (migration, published API, data model) plus one clause on why. Tells the future reader how much evidence they need before re-litigating.
- **Consequences vs Constraints**: Consequences = what we _accepted_ by deciding. Constraints = rules we worked _within_.
- **No manufactured downsides**: trust `Alternatives rejected` to carry the trade-off load. Thin filler is worse than asymmetry.

## Write for skimmability

Read `~/.claude/skills/_shared/skimmable-writing.md` (single source of truth for the skimmability rules) and apply it in full. ADR-specific additions:

- **One Diátaxis mode**: ADRs are **explanation** (_why_ we decided). Do NOT mix in state-of-code reference — that's eng-arch's job. Cross-link instead.
- **Headings = answers**, ADR flavor: `Status: Accepted` not `Status field`. `FormData Content-Type footgun` not `Implementation note 3`.
- **Per-section line caps** (hard — if you blow it, you're writing the wrong section): TL;DR ≤ 3 sentences. Problem ≤ 8. Decision ≤ 8. Assumptions ≤ 6. Consequences ≤ 10. Alternatives ≤ 12. Patterns ≤ 12. Constraints ≤ 8.
- **Target 100–140 lines** at creation (Addenda growth is exempt — it's append-only history). Past that, you're including state-of-code material that belongs in eng-arch (Mega-ADR anti-pattern).

## Template

```markdown
# IQ-XXX: [Feature name from ticket]

- **Status**: Accepted
- **Supersedes**: [IQ-YYY](link) — omit if none
- **Ticket**: [IQ-XXX](jira-url) — from `**URL:**` in the ticket; if no URL is recorded, use the key as plain text (do NOT invent a tracker URL)
- **PR**: [repo#NNN](pr-url) — or `(pending)`
- **Date**: MM-DD-YYYY
- **Reversibility**: two-way door — [one clause] | one-way door — [one clause]

## TL;DR

[≤3 sentences. Written last.]

## Problem

[1–2 paras]

## Decision

[1–2 paras]

## Assumptions

- [Checkable condition: "valid while …" / "revisit if …"]

## Consequences

### Easier

- [what this enables / makes faster / safer]

### Watch out for

- [latent risks, ongoing friction, drift, hidden coupling]

## Alternatives rejected

- **[Option]** — [why not, 1–3 sentences]

## Patterns

### To follow

- `path/to/file.ts:42` — [what / why right]

### To avoid

- `path/to/file.ts:99` — [what / why wrong]

## Constraints

- [Non-obvious limit]

## Related

[Omit unless eng-arch updated]

- Eng-arch: `docs/eng-arch/[subsystem].md`
```
