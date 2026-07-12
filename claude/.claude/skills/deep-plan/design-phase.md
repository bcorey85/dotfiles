# Phase D — Design (inline playbook)

Interactive design discussion producing the highest-leverage artifact: a ~200 line design document capturing every decision before code is written. You are now a participant — read artifacts freely. Force every decision to be explicit; do not outsource the thinking.

## Inputs

Read FULLY (no limit/offset): `DIR/IQ-XXX-00-ticket.md` and `DIR/IQ-XXX-02-research.md`.

## Step 0 — Framing pass (the user speaks first — MANDATORY, blocking)

Read `~/.claude/skills/_shared/framing-pass.md` and run the step it describes **before you form or state any view of your own**: the user's rough approach, the one thing it makes worse, the fork they're unsure about.

**HARD STOP.** No counter-priming, no draft, no presentation, no candidate design named in your output until the user has answered. The Q→R isolation upstream protects YOUR context from the goal; this step protects the USER'S design from you. Getting the second one wrong wastes the first: an artifact whose every decision the user merely ratified is not meaningfully better for having been researched blind.

You have read the ticket and research and the user has not — that asymmetry is exactly why you must not go first. Your first words after reading are a question, not a proposal.

Record the answer verbatim; it becomes the `## Framing` section of the design doc and the basis for every owner tag in it.

## Counter-priming check (after the framing, before presenting)

Name three implementation approaches that are NOT in scope for this design. If you can't name three, the research output may have narrowed the design space — widen your thinking before proceeding. Include them in the initial presentation under "Out-of-scope approaches considered". If you genuinely cannot produce three, say so explicitly — that is diagnostic information about R's framing, not a step to skip.

## Initial Presentation (MANDATORY — before writing anything)

```
Based on the ticket and research, here's my understanding:

**Current State**: [what exists today, from research, with file:line refs]

**Desired End State**: [what the system looks like after we're done]

**Your approach — my verdict**: [sound / sound with caveats / wrong]
[why, with file:line refs. If the research contradicts their framing, LEAD
with that: they need to know their anchor is wrong before they defend it.]

**Out-of-scope approaches considered**: [the three from the counter-priming check, one line each]

**Patterns I found** (confirm these are the RIGHT ones to follow):
- [Pattern] — `file:line` — [brief]

**Patterns to AVOID**:
- [Anti-pattern] — `file:line` — [why]

**Design Questions** (need your input before I can proceed):
1. [Question, framed against their approach per the rule below]
```

## Framing the design questions (not an open menu)

The user named an approach in Step 0. These questions STRESS-TEST it; they do
not re-elicit it. Three cases, and the framing differs in each:

- **Research supports the framing** → state the decision as following from it
  and move on. Do not manufacture a choice to look even-handed.
- **Research breaks the framing** → lead with the failure, with refs: "you
  said X; here's the case where X breaks." Then the alternative. The user is
  defending or abandoning their own position — a real decision either way.
- **Framing is silent on it** → a genuine menu: options with pros/cons and
  your recommendation, recommendation first. This is the only case where you
  go first.

  **Check the menu is live before you show it.** If a constraint you found in
  research has already killed every option but your recommendation, this is not
  a menu — say so: "a constraint already decided this; here's what it killed
  and why." Presenting dead options as live ones manufactures a choice, and the
  user's "sounds right" then gets recorded as judgment they never exercised.

Tag every resolved decision by the tests in
`~/.claude/skills/_shared/design-decision-format.md` § Owner tags — read them.
The tags key on whose judgment shaped the outcome, NOT on which of the three
cases above produced the question.

## Review before presenting (MANDATORY)

Before showing the presentation to the user, draft it to `DIR/.design-draft.md` and run the review loop (`${CLAUDE_SKILL_DIR}/review-loop.md`, **Design presentation** checklist, `phase=design`; inputs: the draft + research + ticket — NOT the **Design document** checklist, which guards the written doc later in this file). Fix what it flags (max 2 rounds), then present the corrected version — this is why the human's time at the gate is spent on judgment, not catching unresolved refs or leading questions. Log the verdict (`phase=design`). Remove the draft after presenting.

Then present, and wait for user responses. Ask follow-ups. Do NOT proceed until every question is answered.

## Write the Design Document

Only after ALL questions are resolved, write `DIR/IQ-XXX-03-design.md`:

```markdown
# Design: [Feature Name]

**Ticket**: DIR/IQ-XXX-00-ticket.md (IQ-XXX)
**Research**: DIR/IQ-XXX-02-research.md
**Date**: YYYY-MM-DD
**Status**: draft

## Framing

<!-- The user's Step 0 framing, verbatim: the approach they named, the
trade-off they accepted, the fork they were unsure about — plus your verdict
on it after research (sound / sound with caveats / wrong, and why). This is
what makes the owner tags below auditable rather than asserted. -->

## Current State

[from research, with file:line refs]

## Desired End State

[after implementation + how to verify done]

## Patterns to Follow

- [pattern — file:line — brief]

## Patterns to AVOID

- [anti-pattern — why]

## Design Decisions

<!-- Every decision uses the four-field block from
~/.claude/skills/_shared/design-decision-format.md (shared with /eng-spec):
Choice / Reasoning (+ owner tag) / Alternatives rejected / Trade-off accepted.
Owner tag is exactly one of User-originated | User-ratified | Locked. -->

### 1. [Topic]

**Choice**: [decided]
**Reasoning**: [why, referencing user input] (User-originated|User-ratified|Locked)
**Alternatives rejected**: [considered and why not]
**Trade-off accepted**: [what this choice makes worse, stated plainly]

## Approaches Considered and Not Taken

<!-- The three counter-primed approaches, carried through from the
presentation. One line each: the approach, and the concrete failure mode that
ruled it out. This is the section that stops the next reader from re-proposing
what you already rejected — an alternative that exists only in the chat is an
alternative that will be litigated again. -->

## Constraints

- [technical, from research] / [business, from ticket]
- [external contracts: NAME every provider/API contract this design touches
  and the invariant it imposes (e.g. message-format pairing rules, rate
  limits, ordering guarantees) — and what breaks if violated. "None" must be
  stated explicitly, not implied by omission.]

## Open Risks

- [what implementation might surface]
```

## Review the written design (MANDATORY — this is where the alarm fires)

After writing `IQ-XXX-03-design.md`, run the review loop once more
(`${CLAUDE_SKILL_DIR}/review-loop.md`, **Design document** checklist; inputs:
design + research + ticket). Fix what it flags (max 2 rounds) and log the
verdict as `phase=design-doc` — a SEPARATE line from the presentation review's
`phase=design`.

If it ESCALATES (issues survive 2 rounds), **stop and surface them to the user
before you move on.** There is no presentation left to fold them into — that
already happened — and Phase S runs with no gate of its own, so an unsurfaced
issue here rides all the way to the Plan gate inside a design everyone assumes
was reviewed.

If the reviewer reports the **ratification alarm**, do not silently fix it —
surface the canonical report line to the user, verbatim, before you move on.
Threshold, fire conditions, and the two report lines are owned by
`~/.claude/skills/_shared/design-decision-format.md` § The ratification alarm:
read it and use its words, rather than paraphrasing the finding into something
softer. It never blocks; it never gets re-tagged away.

**"Before you move on" is deliberately not "before Phase S."** This section is
re-entered from Phase P's design-gap round trip (`SKILL.md`), by which time
Phase S has already run — so "stop before Phase S" would be a no-op there, and
"continue to Phase S" would send you backwards. Both stops mean the same thing
wherever they fire: surface to the user, then return to whatever step sent you
here. From Phase D that is Phase S; from the round trip it is the next step of
the round trip.

## What NOT To Do

- Do NOT propose, sketch, or name an approach before the Step 0 framing is answered — that inverts the whole phase. Your first output after reading the artifacts is a question.
- Do NOT write the design doc without asking questions first — that's the whole point.
- Do NOT make design decisions unilaterally — present options, get user input.
- Do NOT tag a decision `(User-originated)` because the user agreed with you. Agreeing with your recommendation is ratification — a legitimate outcome, and mislabeling it is what makes the audit trail worthless. Origination is the § Owner tags test: their input changed the outcome from what you'd have written alone.
- Do NOT include implementation details (phases, file changes) — that's Phase S.
- Do NOT exceed ~200 lines — concise alignment, not exhaustive spec.

When saved, continue directly to Phase S (no `/clear`).
