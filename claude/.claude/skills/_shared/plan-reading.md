# Reading a Plan (phase-scoped — binds every single-phase consumer)

How a plan is READ (`plan-format.md` owns the shape).

Consumers: `/code` (step 2 orchestrator read, step 3 coder dispatch),
`coder-core` (workflow step 1).

## The rule

Single-phase work reads shared sections + own phase; skips sibling sections.

**THREE contiguous ranges, not ten sections** — shared sections sit BEFORE Phase 0, cross-cutting AFTER the last phase:

1. **Line 1 → end of `## Phase 0: Contracts`** — Overview through contracts. (No Phase 0 → line 1 → first `## Phase` heading.)
2. **Your own `## Phase N:` section.**
3. **`## Testing Strategy` → EOF** — also carries `Plan Deviations` and
   `References`.

**Mechanics**: `rg -n '^## ' <plan>` gives every section line number (and answers multi-phase) in one call. Subtract adjacents for the three ranges, `Read` with `offset`/`limit`. Whole-file-read-plus-mental-skip saves nothing.

Sibling internals are, by construction, not your input — Phase 0 IS the coordination surface.

## The two fences

**Depending on sibling internals is a finding, not a license to widen.** Missing Phase-0 contract or non-vertical slices — coders report `PLAN-IMPACT`, others surface it. Silent workarounds hide the authoring gap.

**Whole-plan consumers exempt** (`plan-verifier` branch scope, `/test-audit`, any cross-phase auditor).