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

- `## Phase Status` is mandatory — `/code` uses it as the durable record of
  "which phase is next" across `/clear` boundaries. Never delete it. Consumers
  find it by HEADING, not position: in `/eng-spec`'s `spec.md` it is hoisted to
  the top of the file (above the judgment layer) so a peek shows progress
  immediately. In a standalone plan it sits where the template below puts it.
- Every Phase Status line carries a `(risk: low|high)` tag.
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
  slices follow in dependency order. Phase 0 is always `(risk: high)` — it IS
  the public-contract tier — and is FROZEN at plan approval: implementers
  changing Phase 0 content mid-plan is a stop-and-surface Plan Deviation,
  never a silent edit. Parallel coder fan-out is allowed only after the
  skeleton phase completes. Single-slice plans with no coordination surface may fold
  contracts into Phase 1 — state so explicitly. Front-load only the surface
  between slices; internal design stays inside its slice.
- A phase with no user-observable behavior (migration-only, infra-only — the
  one legitimate single-layer case) carries its FULL verification in
  Automated Verification and states `Manual Verification: N/A (infra-only)`
  explicitly. An empty Manual Verification section is an authoring gap; the
  N/A line marks the behavioral-gate skip as deliberate.
- Success Criteria are TESTABLE assertions — each specifies HOW to verify
  with the project's real commands (from project CLAUDE.md / package
  scripts), never generic placeholders.
- Manual Verification items are DRIVEABLE scenarios — exact command, request,
  or interaction plus expected result. Items only a human can judge (visual
  polish, UX feel) must say so explicitly so they route to the human-only
  list.
- Every plan ends with the four mandatory closing phases (Refactor → Verify →
  Orient → Recap) from `~/.claude/skills/_shared/closing-phases.md`, appended
  after the last feature phase and numbered continuously. Not negotiable, never
  omitted — include them in `## Phase Status` and as full Phase sections.

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
- [ ] Phase 2: [name] (risk: low|high)

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

## Acceptance Stubs

<!-- Omit this section entirely if the ticket has no behavioral criteria. -->

- **Spec file(s)**: `path or glob (feature-root spec file, or feature-local specs/ dir)`
- **Primitive**: [the project runner's todo/pending marker]
- **Count command**: `<exact command that prints the remaining-stub count>`
- **Stubs** (one per ticket acceptance criterion; domain language, no ticket keys):
  - "[behavior sentence]"

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

Phases that flip acceptance stubs list which ones; the final phase's
Automated Verification must include the stub count command returning zero.

#### Automated Verification:

- [ ] **Build-verified**: build succeeds with zero errors — `<project build cmd>`
- [ ] **Test-verified**: [specific test name/pattern] passes — `<project test cmd>`
- [ ] **Lint/type-verified**: no new errors — `<project lint/typecheck cmd>`

#### Manual Verification:

- [ ] **Manual-verified**: [scenario] — "hit [endpoint/UI flow], confirm [expected behavior]"

**All phases: an agent verifier executes these items after the drift gate, tagging each `agent-verified` (with evidence) or `human-only`. High-risk phases: human sign-off reviews the evidence plus human-only items before proceeding. Low-risk phases: the human-only remainder defers to the `/verify` review packet before the PR opens.**

---

[Same structure per remaining phase...]

## Testing Strategy

[Unit tests, E2E tests, manual steps]

## Plan Deviations

<!-- Created on first deviation; absent until then. One dated entry per
PLAN-IMPACT finding resolved via user question during implementation:
finding (assumed → found), decision, owner. /verify reconciles the diff
against the plan AS AMENDED here; the ADR inherits this record. -->

## References

- [upstream artifact paths]
```
