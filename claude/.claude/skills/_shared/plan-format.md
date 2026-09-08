# Shared Plan Format (single source of truth)

The implementation-plan artifact contract. Producer `/eng-spec`; consumers `/code` (phase gates), `/verify` (reconciliation), humans.

## Risk tiers (assigned per phase, recorded on its Phase Status line)

- `high`: touches migrations or data mutation, auth/security surface, public
  API contracts, irreversible operations, or cross-service boundaries.
- `low`: internal logic, UI, tests, easily-reverted config.
- When in doubt, `high`; untagged = high. `low` resumes mechanically, `high` needs human sign-off.

## Format rules (hard)

- `## Phase Status` is mandatory — never delete it. Consumers find it by HEADING, not position (hoisted to top in `spec.md`).
- Every Phase Status line carries a `(risk: low|high)` tag.
- A phase MAY add `(reviewers: security[, perf])` — the PRIMARY dispatch signal for `security-reviewer`, which never infers from paths. Declare on authz/tenancy changes, guard opt-outs, secrets. Additive only: omitting it never suppresses a forced pass.
- Phases are VERTICAL slices (each independently verifiable end-to-end),
  never horizontal layers.
- Keep each phase signable in one sitting — past ~8–10 semantic files (churn excluded), split on a natural seam into dependency-ordered slices, unless splitting loses end-to-end verifiability; then append `— atomic: <why>`.
- Multi-phase plans open with `Phase 0: Contracts` — the coordination surface
  between slices/streams (shared types, schemas, API shapes, migration
  sketches) as committable content, not prose — then `Phase 1: Walking
skeleton`, the thinnest end-to-end path (`/code` stops after it for calibration). Phase 0 is `(risk: high)` and FROZEN at approval — mid-plan changes are stop-and-surface Plan Deviations, never silent edits. No parallel fan-out before the skeleton lands. Single-slice plans may fold contracts into Phase 1 (state so). Front-load only the inter-slice surface.
- A behaviorless phase (migration/infra-only — the one legitimate single-layer case) carries FULL verification in Automated Verification and states `Manual Verification: N/A (infra-only)` — an empty section is an authoring gap.
- Success Criteria are TESTABLE assertions — each specifies HOW to verify
  with the project's real commands (from project CLAUDE.md / package
  scripts), never generic placeholders.
- Manual Verification items are DRIVEABLE scenarios — exact command, request,
  or interaction plus expected result. Items only a human can judge (visual
  polish, UX feel) must say so explicitly so they route to the human-only
  list.
- Every plan ends with the four mandatory closing phases (Refactor →
  Test audit → Verify → Recap) from `~/.claude/skills/_shared/closing-phases.md`, appended
  after the last feature phase and numbered continuously — in `## Phase Status`
  and as full Phase sections.

## Reading a plan

Rule and mechanics: `plan-reading.md`.

## Template

Header links: whichever upstream artifacts exist. Do not invent links.

```markdown
# [Feature Name] Implementation Plan

**Ticket**: [path or key]
**Date**: YYYY-MM-DD
[optional upstream artifact links]

## Overview

[1-2 sentence summary]

## Phase Status

<!-- /code updates per phase. Source of truth for "which phase is next". Do not delete. -->

- [ ] Phase 0: Contracts — frozen at plan approval (risk: high)
- [ ] Phase 1: Walking skeleton — thinnest path through every Phase 0 contract (risk: low|high)
- [ ] Phase 2: [name] (risk: low|high) (reviewers: security)

<!-- Mandatory closing phases (closing-phases.md), renumbered after the last feature phase: -->

- [ ] Phase N: Refactor pass — /refactor cleanup sweep (risk: low)
- [ ] Phase N+1: Test audit — /test-audit cross-phase test gate (risk: high)
- [ ] Phase N+2: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage, no gates (risk: low)

## Current State Analysis

[Brief]

## Desired End State

[Brief, with verification criteria]

## What We're NOT Doing

[Scope boundaries]

## Acceptance Criteria

<!-- Omit when the ticket has no behavioral criteria. Written by user + main thread after final, BEFORE any coder — never later, never by the satisfying agent. 3-8; more = two tickets. -->

The criteria live in `docs/plans/<slug>/acceptance-criteria.md` as prose with stable ids, written by Phase 7.5. Name the file here and nothing more — never restate the criteria, never copy their ids into code.

- **Criteria file**: `docs/plans/<slug>/acceptance-criteria.md`

The closing Verify phase reconciles every id against the real suite
(`_shared/closing-phases.md`), matching behavior, not markers. A covering test
asserts at the public boundary a user or caller reaches, never an internal
function. **No mocks inside such a test.**

## Implementation Approach

[Strategy and key decisions]

## Phase 1: [Name]

### Overview

[What this phase accomplishes]

### Changes Required:

#### 1. [Component/File]

**File**: `path/to/file.ts`
**Changes**: [specific changes, with code blocks to add/modify]

**Never list a test file here** — the coder writes no tests; the `test-writer` takes assertions from the plan. A test that must change goes in Success Criteria as a behavior.

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

[Approach only. A unit that MUST be tested needs a behavior in Success Criteria or an acceptance criterion.]

## Plan Deviations

<!-- Created on first deviation; absent until then. One dated entry per resolved PLAN-IMPACT (assumed → found, decision, owner). `/verify` reconciles against the plan AS AMENDED here. -->

## References

- [upstream artifact paths]
```
