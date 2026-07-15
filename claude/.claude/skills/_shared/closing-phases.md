# Mandatory Closing Phases (single source of truth)

Every `/eng-spec` plan ends with these FOUR phases, in this exact order, after
the last feature phase — **not negotiable, never omitted**, however small the
feature. They are real `## Phase Status` entries (checkboxes `/code` advances
through) with full Phase sections; reaching one, `/code` invokes the named
skill instead of dispatching a coder. Number them continuing from the last
feature phase (feature ends at Phase 3 → these are 4–7).

## The four phases

1. **Refactor pass** (risk: low) — `/refactor +deep` over the **whole branch
   diff**, backend **and** frontend in one sweep. DRY duplication, delete dead
   scaffolding, tighten names — no behavior change. **Root-cause gate:** adding
   a cast or `?? default` to paper over a fixable wide type or loose structure
   is a failed refactor; fix the source — `/review` bounces it. Success
   Criteria: quality checks green, no new cast/fallback dodging a root cause.

2. **Verify pass** (risk: high) — confirm the work actually does what the plan
   called for. Two complementary checks, both required:
   - **Branch-wide deep review** — dispatch ONE `code-reviewer-deep` (omit
     `model`) over the assembled branch diff (`git diff <base>...HEAD`) — the
     only fresh-eyes look at cross-phase interactions the phase-scoped per-loop
     reviews miss. Findings route through `/review`'s severity gating.
   - `/verify` — reconcile the shipped diff against the ticket/plan
     (completeness, every Acceptance Stub flipped), run the plan's Automated
     Verification commands, and emit the **human smoke-test checklist** (ACs
     + all human-only Manual Verification items).
     Success Criteria: deep review clean, reconciliation reports no missing
     work, smoke-test checklist delivered.

3. **Orient pass** (risk: low) — `/orient` to rebuild the mental map diff
   review misses: how the change connects to surrounding code, what it touches,
   what a reader needs next. Success Criteria: orientation summary produced;
   surprise coupling surfaced as a follow-up.

4. **Recap** (risk: low) — `/branch-recap` reassembles the branch into one
   pre-PR artifact: the **cross-phase test audit** (cull + coverage-net — the
   half of test-intent no phase judges locally), `/stage` triage of the closing
   phases' residue, and the recap receipt. Runs no gates — each already fired
   where its oracle was sharper. Success Criteria: recap produced; residue
   queue handed to the user.

Nothing after this is a phase. `/adr` is **post-PR** — it wants the PR link.

## Phase Status lines (copy verbatim, renumbering)

```markdown
- [ ] Phase N: Refactor pass — /refactor +deep whole-branch sweep, root-cause gate (risk: low)
- [ ] Phase N+1: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+2: Orient pass — /orient situate the change (risk: low)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage (risk: low)
```
