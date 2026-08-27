# Mandatory Closing Phases (single source of truth)

Every `/eng-spec` plan ends with these FOUR phases, in this exact order after
the last feature phase — **not negotiable, never omitted**. They are real
`## Phase Status` entries with full Phase sections; reaching one, `/code`
invokes the named skill instead of dispatching a coder. Number them continuing from the last
feature phase (feature ends at Phase 3 → these are 4–7).

## The four phases

1. **Refactor pass** (risk: low) — `/refactor +deep` over the **whole branch
   diff**, backend **and** frontend in one sweep. DRY duplication, delete dead
   scaffolding, tighten names — no behavior change. **Root-cause gate:** adding
   a cast or `?? default` to paper over a fixable wide type or loose structure
   is a failed refactor; fix the source — `/review` bounces it.

   **Concentration gate.** Group `git diff --numstat <base>...HEAD` by module;
   if the largest module has **≥100 added lines**, also run
   `/refactor simplify <that module>` — that module alone, after the branch
   sweep. Otherwise skip it and report the largest count. Never widen to a
   second module, never pass the branch diff (`complexity-reviewer` refuses a
   diff bound). Simplify findings are opt-in per finding, the user's call;
   accepting one makes this phase `risk: high` — the no-behavior-change
   contract covers the DRY sweep only.

   Success Criteria: quality checks green, no new cast/fallback dodging a root
   cause, concentration gate evaluated (module named, or largest count stated).

2. **Verify pass** (risk: high) — confirm the work actually does what the plan
   called for. Two complementary checks, both required:
   - **Branch-wide deep review** — dispatch ONE `code-reviewer-deep` (omit
     `model`) over the assembled branch diff (`git diff <base>...HEAD`) — the
     only fresh-eyes look at cross-phase interactions the phase-scoped per-loop
     reviews miss. Findings route through `/review`'s disposition routing.
   - `/verify` — reconcile the shipped diff against the ticket/plan
     (completeness), run the plan's Automated Verification commands, and emit the
     **human smoke-test checklist** (all human-only Manual Verification items).
   - **Acceptance-criteria reconciliation** — for every id in
     `docs/plans/<slug>/acceptance-criteria.md`, name the test that covers it
     (`file:line`) or report it MISSING. This is the only check that the criteria
     written before implementation actually got implemented; nothing earlier in
     the pipeline enforces it, because the criteria deliberately live outside the
     test tree. A criterion under `## Manual only` is satisfied by appearing on
     the smoke-test checklist, not by a test. MISSING is a phase failure, not a
     note — either a test is owed or the user retires the criterion on the
     record.

     Match on **behavior, not on markers**: the tests carry ordinary names and
     contain no criterion ids (`_shared/code-vocabulary.md`), so the mapping is
     read and judged, never grepped.

     Success Criteria: deep review clean, reconciliation reports no missing work,
     every acceptance criterion mapped to a test or explicitly retired,
     smoke-test checklist delivered.

3. **Test audit** (risk: high) — `/test-audit`, the cross-phase test gate: cull
   test spam, catch net-removed coverage, sweep weak assertions against the plan —
   the half of test-intent no phase judges locally. A gate; findings route to
   `/fix` or a `test-writer` re-dispatch, and it hands a receipt to the Recap.
   Success Criteria: audit run with its denominator stated; every finding routed.

4. **Recap** (risk: low) — `/branch-recap` reassembles the branch into one
   pre-PR handoff: `/stage` triage of residue, the deferred-findings queue, the
   recap receipt. Reads the branch's own process, never the codebase. Situating
   is `/orient`'s job, on demand, never a phase; recap consumes an orient map if
   one exists. Runs no gates. Success Criteria: recap produced; residue queue
   handed to user.

Nothing after this is a phase. `/adr` runs **pre-PR**, shipping in the code's PR.

## Phase Status lines (copy verbatim, renumbering)

```markdown
- [ ] Phase N: Refactor pass — /refactor +deep whole-branch sweep, root-cause gate (risk: low)
- [ ] Phase N+1: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+2: Test audit — /test-audit cross-phase test gate (risk: high)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage, no gates (risk: low)
```
