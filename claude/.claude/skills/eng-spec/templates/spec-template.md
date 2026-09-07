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

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

One paragraph on what this accomplishes.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [ ] Phase 0: Contracts — frozen at plan approval (risk: high)
- [ ] Phase 1: Walking skeleton (risk: low|high)
- [ ] Phase 2: [name] (risk: low|high)
- [ ] Phase N..N+3: Refactor → Verify → Test audit → Recap (closing-phases.md)

## Decisions

<!-- Copied verbatim from 03-decisions.md's ## Resolved. Four-field block per decision (Choice / Reasoning / Alternatives rejected / Trade-off accepted) — never a one-line-rationale table. -->

## Approaches Considered and Not Taken

<!-- The architect's counter-primed approaches, one line each (approach + ruling-out failure mode). Whole-feature approaches, not within-decision options. If fewer than three, say how many. -->

## Constraints

<!-- Fixed-before-design non-negotiables: platform limits, existing contracts. A "decision" with no real alternative belongs HERE.

Self-sufficient: probe-verified facts an implementation step needs go here with evidence (coders don't read the ledger), each tagged `exercised` (observed) or `declared-only` (asserted). -->

## External Contracts

<!-- Mandatory: every touched provider/API/platform contract + its invariant + what breaks if violated, claims tagged `exercised`/`declared-only`. Wide-blast-radius internal invariants too. "None" stated explicitly. -->

## Approach

- Breakdown by area — area framing lives in THIS section only; the Implementation
  Plan below slices vertically, never by area
- Specific patterns to follow
- API contract (fullstack: fixed here, frontend designs against it)

## Dependencies

- External packages to install
- Internal modules to build on

## Implementation Plan

<!-- From here down, plan-format.md IN FULL, with ONE deviation: `## Phase Status` lives at the TOP of this file, not here. Vertical phases with risk tags, Changes Required + Success Criteria (Automated/Manual Verification, real commands), `Acceptance Criteria` naming `acceptance-criteria.md` when behavioral. Ends with the four closing phases (closing-phases.md) — never omitted. -->
```
