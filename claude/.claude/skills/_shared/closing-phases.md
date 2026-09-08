# Mandatory Closing Phases (single source of truth)

Every `/eng-spec` plan ends with these FOUR phases, in order after the last feature phase — **not negotiable, never omitted**. Real `## Phase Status` entries with full sections; `/code` invokes the named skill instead of a coder. Numbered continuing from the last feature phase.

## The four phases

1. **Refactor pass** (risk: low) — `/refactor +deep` over the **whole branch diff** (backend + frontend, one sweep): DRY duplication, dead scaffolding, names — no behavior change. **Root-cause gate:** a cast/`?? default` papering a fixable wide type or loose structure fails; fix the source.

   **Concentration gate.** Group `git diff --numstat <base>...HEAD` by module; run `/refactor simplify <one module>` when EITHER: 1. **Concentrated**: largest module **≥100 added lines**. 2. **Distributed**: branch **≥300 added lines** (excluding lockfiles, generated files, and test-only files) with no module at 100 — dispatch the largest anyway. Else skip, report both counts. Never a second module, never the branch diff (`complexity-reviewer` refuses diff bounds). Cross-module deletability reasons go in the report, not a re-dispatch. Simplify findings are opt-in; accepting one makes this phase `risk: high` — the no-behavior-change contract covers the DRY sweep only.

   Success Criteria: quality checks green, no new cast/fallback dodging a root
   cause, concentration gate evaluated (module dispatched with the trigger
   named, or both counts stated).

2. **Test audit** (risk: high) — `/test-audit`: cull spam, catch net-removed coverage, sweep weak assertions — the half of test-intent no phase judges. Findings → `/fix` / `test-writer`; receipt → Recap. Success Criteria: denominator stated, every finding routed.

3. **Verify pass** (risk: high) — two complementary checks, both required:
   - **Branch-wide deep review** — ONE `code-reviewer-deep` (omit `model`) over the branch diff: the only fresh-eyes look at cross-phase interactions. Findings via `/review` routing.
   - `/verify` — reconcile the shipped diff against the ticket/plan
     (completeness), run the plan's Automated Verification commands, and emit the
     **human smoke-test checklist** (all human-only Manual Verification items).
   - **Acceptance-criteria reconciliation** — per id: name the covering test (`file:line`) or MISSING. `## Manual only` items are satisfied via the smoke-test checklist. MISSING fails the phase — a test is owed or the user retires the criterion on record.

     Match on **behavior, not markers** — no ids to grep; read and judged.

     Success Criteria: deep review clean, reconciliation reports no missing work,
     every acceptance criterion mapped to a test or explicitly retired,
     smoke-test checklist delivered.

4. **Recap** (risk: low) — `/branch-recap`: `/stage` triage, deferred queue, recap receipt — from the branch's own process, never the codebase (`/orient` on demand). No gates. Success Criteria: recap produced, residue handed over.

Nothing after this is a phase. `/adr` runs **pre-PR**, shipping in the code's PR.

## Phase Status lines (copy verbatim, renumbering)

```markdown
- [ ] Phase N: Refactor pass — /refactor +deep whole-branch sweep, root-cause gate (risk: low)
- [ ] Phase N+1: Test audit — /test-audit cross-phase test gate (risk: high)
- [ ] Phase N+2: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage, no gates (risk: low)
```
