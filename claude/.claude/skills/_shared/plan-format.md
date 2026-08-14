# Shared Plan Format (single source of truth)

The implementation-plan artifact contract. Producer: `/eng-spec`. Consumers:
`/code` (phase-boundary gates key off `## Phase Status` risk tags and
`#### Manual Verification` sections), `/verify` (plan↔diff reconciliation),
and the human skimming phases.

## Risk tiers (assigned per phase, recorded on its Phase Status line)

- `high`: touches migrations or data mutation, auth/security surface, public
  API contracts, irreversible operations, or cross-service boundaries.
- `low`: internal logic, UI, tests, easily-reverted config.
- When in doubt, `high`. `/code` gives `low` a mechanical resume (machine
  gates only) and `high` a human sign-off with manual verification. An
  UNTAGGED phase is treated as high.

## Format rules (hard)

- `## Phase Status` is mandatory — never delete it. Consumers find it by HEADING, not position: in `/eng-spec`'s `spec.md` it is hoisted to the top (above the judgment layer); in a standalone plan it sits where the template below puts it.
- Every Phase Status line carries a `(risk: low|high)` tag.
- A phase MAY add `(reviewers: security[, perf])` — the PRIMARY dispatch signal for `security-reviewer`, which never infers a security surface from paths or keywords. Declare it when the phase changes authz/tenancy, opts out of a guard, or handles secrets. Additive only: omitting it never suppresses a forced pass.
- Phases are VERTICAL slices (each independently verifiable end-to-end),
  never horizontal layers.
- Keep each phase's diff signable in one sitting — past ~8–10 semantic files
  (generated/lockfile/rename churn excluded), split on a natural seam into
  dependency-ordered slices, unless it can't without losing end-to-end
  verifiability (walking skeleton, broad rename); then append
  `— atomic: <why>` to its Phase Status line.
- Multi-phase plans open with `Phase 0: Contracts` — the coordination surface
  between slices/streams (shared types, schemas, API shapes, migration
  sketches) as committable content, not prose — then `Phase 1: Walking
skeleton`, the thinnest end-to-end path exercising every Phase 0 contract
  (`/code` stops after Phase 1 for calibration). Remaining
  slices follow in dependency order. Phase 0 is always `(risk: high)` and FROZEN at plan approval: changing Phase 0 content mid-plan is a stop-and-surface Plan Deviation, never a silent edit. Parallel coder fan-out is allowed only after the skeleton phase completes. Single-slice plans with no coordination surface may fold contracts into Phase 1 — state so explicitly. Front-load only the surface between slices; internal design stays inside its slice.
- A phase with no user-observable behavior (migration-only, infra-only — the
  one legitimate single-layer case) carries its FULL verification in
  Automated Verification and states `Manual Verification: N/A (infra-only)`
  explicitly — an empty section is an authoring gap, not a skip.
- Success Criteria are TESTABLE assertions — each specifies HOW to verify
  with the project's real commands (from project CLAUDE.md / package
  scripts), never generic placeholders.
- Manual Verification items are DRIVEABLE scenarios — exact command, request,
  or interaction plus expected result. Items only a human can judge (visual
  polish, UX feel) must say so explicitly so they route to the human-only
  list.
- Every plan ends with the four mandatory closing phases (Refactor → Verify →
  Orient → Recap) from `~/.claude/skills/_shared/closing-phases.md`, appended
  after the last feature phase and numbered continuously — in `## Phase Status`
  and as full Phase sections.

## Reading a plan

Consumers working ONE phase read it phase-scoped — shared sections plus their
own phase, skipping siblings. Rule and mechanics: `plan-reading.md`.

## Template

Header links: include whichever upstream artifacts exist under the eng-spec
task dir (ticket/research/spec paths). Do not invent links to artifacts that
don't exist.

```markdown
# [Feature Name] Implementation Plan

**Ticket**: [path or key]
**Date**: YYYY-MM-DD
[optional upstream artifact links]

## Overview

[1-2 sentence summary]

## Phase Status

<!-- Updated by /code after each phase completes + review passes. Source of truth for "which phase is next" across /clear boundaries. Do not delete. -->

- [ ] Phase 0: Contracts — frozen at plan approval (risk: high)
- [ ] Phase 1: Walking skeleton — thinnest path through every Phase 0 contract (risk: low|high)
- [ ] Phase 2: [name] (risk: low|high) (reviewers: security)

<!-- Mandatory closing phases (closing-phases.md), renumbered after the last feature phase: -->

- [ ] Phase N: Refactor pass — /refactor cleanup sweep (risk: low)
- [ ] Phase N+1: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+2: Orient pass — /orient situate the change (risk: low)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage (risk: low)

## Current State Analysis

[Brief]

## Desired End State

[Brief, with verification criteria]

## What We're NOT Doing

[Scope boundaries]

## Acceptance Criteria

<!-- Omit this section entirely if the ticket has no behavioral criteria.
Written by the user with the main thread after the plan is final and BEFORE any
coder is dispatched — never later, and never by the agent that will satisfy it.
3-8 of them; if there are more, the ticket is two tickets. -->

The criteria live in `docs/plans/<slug>/acceptance-criteria.md` as prose with
stable ids (`AC1`…`ACn`), written by `/eng-spec` Phase 7.5. This section names
the file and nothing more — do not restate the criteria here, and do not copy
their ids into any file under the source tree.

- **Criteria file**: `docs/plans/<slug>/acceptance-criteria.md`

The closing Verify phase reconciles every id against the real test suite
(`_shared/closing-phases.md`), matching on behavior rather than markers. Tests
that cover a criterion assert at its boundary — the public entry point a user or
caller reaches — never an internal function (an internal assertion pins today's
structure and blocks the refactor it should survive). **No mocks inside such a
test.**

## Implementation Approach

[Strategy and key decisions]

## Phase 1: [Name]

### Overview

[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File]

**File**: `path/to/file.ts`
**Changes**: [specific changes, with code blocks to add/modify]

### Success Criteria

A phase that delivers an acceptance criterion states the behavior in its own
words here — never the criterion's id. The closing Verify phase is what maps
criteria to tests.

#### Automated Verification:

- [ ] **Build-verified**: build succeeds with zero errors — `<project build cmd>`
- [ ] **Test-verified**: [specific test name/pattern] passes — `<project test cmd>`
- [ ] **Lint/type-verified**: no new errors — `<project lint/typecheck cmd>`

#### Manual Verification:

- [ ] **Manual-verified**: [scenario] — "hit [endpoint/UI flow], confirm [expected behavior]"

**`/verify` executes these at branch end, tagging each `agent-verified` or `human-only`.**

---

[Same structure per remaining phase...]

## Testing Strategy

[Approach only. Naming a unit here doesn't test it — a unit that MUST be tested
needs a behavior in its phase's Success Criteria, or an acceptance criterion.]

## Plan Deviations

<!-- Created on first deviation; absent until then. One dated entry per
PLAN-IMPACT finding resolved via user question during implementation:
finding (assumed → found), decision, owner. /verify reconciles the diff
against the plan AS AMENDED here; the ADR inherits this record. -->

## References

- [upstream artifact paths]
```
