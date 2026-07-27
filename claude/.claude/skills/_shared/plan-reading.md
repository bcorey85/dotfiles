# Reading a Plan (phase-scoped — binds every single-phase consumer)

Consumer-side counterpart to `plan-format.md`, which owns the artifact's
shape. This file owns how it is READ. Lives outside the guarded planning
budget deliberately: it constrains agents, not the plan.

Consumers: `/code` (step 2 orchestrator read, step 4 coder dispatch),
`coder-core` (workflow step 1).

## The rule

A plan is written to be read one slice at a time. Anyone working a SINGLE
phase reads the shared sections plus their own phase, and skips every sibling
`## Phase N:` section.

**It is THREE contiguous ranges, not ten sections.** The format orders every
shared section BEFORE Phase 0 and every cross-cutting section AFTER the last
phase, so a scoped read is three `Read` calls:

1. **Line 1 → end of `## Phase 0: Contracts`** — one range covering `Overview`,
   `Phase Status`, `Current State Analysis`, `Desired End State`, `What We're
NOT Doing`, `Acceptance Stubs`, `Implementation Approach`, and the contracts.
   (No Phase 0 — a single-slice plan folds contracts into Phase 1 — then it is
   line 1 → the first `## Phase` heading.)
2. **Your own `## Phase N:` section.**
3. **`## Testing Strategy` → EOF** — also carries `Plan Deviations` and
   `References`.

Everything skipped is a sibling `## Phase N:` section.

**Mechanics**: `rg -n '^## ' <plan>` returns every section's line number in one
call — it also answers "is this multi-phase?" without a Read. Subtract adjacent
line numbers to get the three ranges, then `Read` with `offset`/`limit`.
Reading the whole file and mentally skipping saves nothing; the cost is the
read, not the attention.

## Why this is the format's own rule, not an optimization

`Phase 0: Contracts` IS the coordination surface between slices, and
`plan-format.md` states it directly: "front-load only the surface between
slices; internal design stays inside its slice." A sibling phase's internals
are therefore, by construction, not your input.

## The two fences

**A dependency on a sibling's internals is a finding, not a license to widen
the read.** It means Phase 0 is missing a contract, or the phases are not the
vertical slices the format requires. A coder reports it as `PLAN-IMPACT`;
anyone else surfaces it to the user. Silently reading around it hides the
authoring gap that caused it.

**Whole-plan consumers are exempt** — `plan-verifier` at `scope: branch`,
`/branch-recap`'s cross-phase audit, and anything else whose job IS the
cross-phase view. Scoping applies to working a phase, not to auditing a plan.
