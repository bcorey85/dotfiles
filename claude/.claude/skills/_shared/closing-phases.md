# Mandatory Closing Phases (single source of truth)

Every `/eng-spec` plan ends with these FOUR phases, in order after the last feature phase — **not negotiable, never omitted**. Real `## Phase Status` entries with full sections; `/code` invokes the named skill instead of a coder. Numbered continuing from the last feature phase.

## The four phases

1. **Refactor pass** (risk: low) — `/refactor +deep` over the **whole branch diff** (backend + frontend, one sweep): DRY duplication, dead scaffolding, names — no behavior change. **Root-cause gate:** a cast/`?? default` papering a fixable wide type or loose structure fails; fix the source.

   **Concentration gate.** `code-step` computes the added lines per module of `git diff --numstat <base>...HEAD` (excluding lockfiles, generated and build output (dist/, .min.js, snapshots), test-only files, and anything under a `docs/` folder, plans included); run `/refactor simplify <one module>` when EITHER: 1. **Concentrated**: largest module **≥100 added lines**. 2. **Distributed**: branch **≥300 added lines** with no module at 100 — dispatch the largest anyway. Else skip, report both counts. Never a second module, never the branch diff (`complexity-reviewer` refuses diff bounds). Cross-module deletability reasons go in the report, not a re-dispatch. Simplify findings are opt-in; accepting one makes this phase `risk: high` — the no-behavior-change contract covers the DRY sweep only.

   Success Criteria: quality checks green, no new cast/fallback dodging a root
   cause, concentration gate evaluated (module dispatched with the trigger
   named, or both counts stated).

   A scope box diffs two recorded commit ids, never a branch name (`main...HEAD` is empty once the branch merges), and fails on an empty diff: `test -n "$(git diff --name-only <base-sha>..<head-sha>)"`. `plan check` fails a box that diffs a branch name.

2. **Test audit** (risk: high) — `/test-audit`: cull spam, sweep weak assertions — the half of test-intent no phase judges. Findings → `/fix`; receipt → Recap. Success Criteria: denominator stated, every finding routed.

3. **Verify pass** (risk: high) — `/verify-branch` runs both checks, in order:
   - **Branch-wide deep review** — ONE `code-reviewer` over the branch diff, unless one ran since the last change: the only fresh-eyes look at cross-phase interactions. Findings via `/review` routing, logged with `scope=branch-exit`.
   - **Completeness** — reconcile the shipped diff against the ticket/plan
     (completeness), run the plan's Automated Verification commands (a failing command is a gap), and emit the
     **human smoke-test checklist** (all human-only Manual Verification items).
     - **Acceptance-criteria reconciliation** — per id: name the covering test (`file:line`) or MISSING. `## Manual only` items are satisfied via the smoke-test checklist. MISSING fails the phase — a test is owed or the user retires the criterion on record.

       Match on **behavior, not markers** — no ids to grep; read and judged.

   Success Criteria: deep review clean, reconciliation reports no missing work,
   every acceptance criterion mapped to a test or explicitly retired,
   smoke-test checklist delivered.

4. **Recap** (risk: low) — `/branch-recap`: `/stage` triage, deferred queue, recap receipt — from the branch's own process, never the codebase (`/orient` on demand). No gates. Success Criteria: recap produced, residue handed over.

At `skill-done pass`, the session gives one `--evidence` per open Success Criteria item and the script writes it into the plan. For the Refactor pass, `code-step` prints both counts and whether the gate triggers; on a trigger, `skill-done pass` needs `--simplify "<module>; <trigger>"`, where `<module>` is the module `code-step` named (any other is refused). The script writes it under the gate item as `simplify <module> (<trigger>)`; a `--simplify` with no open gate item is refused.

Nothing after this is a phase. `/adr` runs **pre-PR**, shipping in the code's PR.

## Phase Status lines (copy verbatim, renumbering)

```markdown
- [ ] Phase N: Refactor pass — /refactor +deep whole-branch sweep, root-cause gate (risk: low)
- [ ] Phase N+1: Test audit — /test-audit cross-phase test gate (risk: high)
- [ ] Phase N+2: Verify pass — branch-wide deep review + /verify-branch (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage, no gates (risk: low)
```
