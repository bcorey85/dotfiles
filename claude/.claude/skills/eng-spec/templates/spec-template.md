# Spec template

The spec has two layers in ONE file: a judgment layer (what a human reads at the
gate) and an implementation layer (what `/code` executes, in the shared plan
format so its phase gates work).

**`## Phase Status` is hoisted to the top, above both layers** — the one deviation
from `plan-format.md`, which otherwise applies in full.

Everything below the fence is the file to write.

```markdown
# Title

> Jira: JIRAPROJECT-TICKETNUMBER (if applicable)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: YYYY-MM-DD

<!-- Source precedence: on anything concrete — a value, a signature, a command, a
criterion — THIS file wins. The ledger records why a choice was made, not what
the coder builds. A reader who finds them disagreeing has found a spec bug;
report it rather than picking the one that sounds more considered. -->

## Summary

One paragraph on what this accomplishes.

## Phase Status

<!-- Hoisted here from the Implementation Plan below so opening the file answers
"where are the agents?" on the first screen. It is the one section that changes
after the spec is written — /code ticks it as phases land — and the source of
truth for "which phase is next" across /clear boundaries. Do not move it back
down. Lines and risk tags follow plan-format.md exactly. -->

- [ ] Phase 0: Contracts — frozen at plan approval (risk: high)
- [ ] Phase 1: Walking skeleton (risk: low|high)
- [ ] Phase 2: [name] (risk: low|high)
- [ ] Phase N..N+3: Refactor → Verify → Test audit → Recap (closing-phases.md)

## Decisions

<!-- Copied verbatim from 03-decisions.md's ## Resolved section. Every decision
uses the four-field block from ~/.claude/skills/_shared/design-decision-format.md:
Choice / Reasoning / Alternatives rejected / Trade-off accepted. Never a table
with one-line rationales. -->

## Approaches Considered and Not Taken

<!-- The architect's three counter-primed approaches, one line each: the
approach, and the concrete failure mode that ruled it out. Different axis from a
decision's "Alternatives rejected" — these are whole approaches to the feature,
not options within one decision. If the architect could not name three, say so
and say how many it named. -->

## Constraints

<!-- What was fixed before design began and could not be traded away: platform
limits, existing contracts, non-negotiables. A "decision" with no real
alternative belongs HERE — if you cannot name an option a constraint killed, it
was never a decision.

Self-sufficient: any probe-verified fact an implementation step depends on is
stated here with its evidence, not left in 03-decisions.md. A coder reads this
file and not the ledger. Tag each such fact `exercised` (someone ran it and
observed the behavior) or `declared-only` (documentation, schema text, or
in-repo precedent asserts it). -->

## External Contracts

<!-- Mandatory: every provider/API/platform contract touched + the invariant it
imposes + what breaks if violated, each acceptance claim tagged `exercised` or
`declared-only`. Internal invariants with blast radius (identity construction,
hidden couplings) belong here too. "None" must be stated explicitly. -->

## Approach

- Breakdown by area — area framing lives in THIS section only; the Implementation
  Plan below slices vertically, never by area
- Specific patterns to follow
- API contract (fullstack: fixed here, frontend designs against it)

## Dependencies

- External packages to install
- Internal modules to build on

## Implementation Plan

<!-- From here down, follow ~/.claude/skills/_shared/plan-format.md IN FULL —
with ONE deviation: its `## Phase Status` section lives at the TOP of this file
(above ## Decisions), not here. Everything else is unchanged: vertical phases with
(risk: low|high) tags, per-phase Changes Required + Success Criteria
(Automated/Manual Verification with the project's real commands), and an
`Acceptance Criteria` section naming `acceptance-criteria.md` when the ticket has
behavioral criteria. This is what /code's phase gates and /verify consume. Every
spec ends with the four mandatory closing phases from
~/.claude/skills/_shared/closing-phases.md (Refactor → Verify → Test audit → Recap;
Recap = /branch-recap) — never omitted. -->
```
