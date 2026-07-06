# Phase D — Design (inline playbook)

Interactive design discussion producing the highest-leverage artifact: a ~200 line design document capturing every decision before code is written. You are now a participant — read artifacts freely. Force every decision to be explicit; do not outsource the thinking.

## Inputs

Read FULLY (no limit/offset): `DIR/IQ-XXX-00-ticket.md` and `DIR/IQ-XXX-02-research.md`.

## Counter-priming check (do this FIRST, before presenting)

Name three implementation approaches that are NOT in scope for this design. If you can't name three, the research output may have narrowed the design space — widen your thinking before proceeding. Include them in the initial presentation under "Out-of-scope approaches considered". If you genuinely cannot produce three, say so explicitly — that is diagnostic information about R's framing, not a step to skip.

## Initial Presentation (MANDATORY — before writing anything)

```
Based on the ticket and research, here's my understanding:

**Current State**: [what exists today, from research, with file:line refs]

**Desired End State**: [what the system looks like after we're done]

**Out-of-scope approaches considered**: [the three from the counter-priming check, one line each]

**Patterns I found** (confirm these are the RIGHT ones to follow):
- [Pattern] — `file:line` — [brief]

**Patterns to AVOID**:
- [Anti-pattern] — `file:line` — [why]

**Design Questions** (need your input before I can proceed):
1. [Question] — A: [option + pros/cons] / B: [...] — Recommended: [pick + why]
```

## Review before presenting (MANDATORY)

Before showing the presentation to the user, draft it to `DIR/.design-draft.md` and run the review loop (`${CLAUDE_SKILL_DIR}/review-loop.md`, **Design** checklist; inputs: the draft + research + ticket). Fix what it flags (max 2 rounds), then present the corrected version — this is why the human's time at the gate is spent on judgment, not catching unresolved refs or leading questions. Log the verdict (`phase=design`). Remove the draft after presenting.

Then present, and wait for user responses. Ask follow-ups. Do NOT proceed until every question is answered.

## Write the Design Document

Only after ALL questions are resolved, write `DIR/IQ-XXX-03-design.md`:

```markdown
# Design: [Feature Name]

**Ticket**: DIR/IQ-XXX-00-ticket.md (IQ-XXX)
**Research**: DIR/IQ-XXX-02-research.md
**Date**: YYYY-MM-DD
**Status**: draft

## Current State

[from research, with file:line refs]

## Desired End State

[after implementation + how to verify done]

## Patterns to Follow

- [pattern — file:line — brief]

## Patterns to AVOID

- [anti-pattern — why]

## Design Decisions

### 1. [Topic]

**Choice**: [decided]
**Reasoning**: [why, referencing user input]
**Alternatives rejected**: [considered and why not]

## Constraints

- [technical, from research] / [business, from ticket]
- [external contracts: NAME every provider/API contract this design touches
  and the invariant it imposes (e.g. message-format pairing rules, rate
  limits, ordering guarantees) — and what breaks if violated. "None" must be
  stated explicitly, not implied by omission.]

## Open Risks

- [what implementation might surface]
```

## What NOT To Do

- Do NOT write the design doc without asking questions first — that's the whole point.
- Do NOT make design decisions unilaterally — present options, get user input.
- Do NOT include implementation details (phases, file changes) — that's Phase S.
- Do NOT exceed ~200 lines — concise alignment, not exhaustive spec.

When saved, continue directly to Phase S (no `/clear`).
