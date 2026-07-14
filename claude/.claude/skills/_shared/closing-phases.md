# Mandatory Closing Phases (single source of truth)

Every implementation plan — from `/eng-spec` —
ends with these FOUR phases, appended after the last feature phase, in this
exact order. They are **not negotiable and never omitted**, regardless of how
small the feature is. They appear as real `## Phase Status` entries (tracked
checkboxes `/code` advances through) and get full Phase sections like any
other phase. When `/code` reaches one, it invokes the named skill instead of
dispatching a coder.

Number them continuing from the last feature phase (e.g. if the feature ends
at Phase 3, these are Phases 4–7).

## The four phases

1. **Refactor pass** (risk: low) — `/refactor` over the code this plan just
   shipped: DRY out duplication, delete dead scaffolding, tighten names.
   Cleanup only, no behavior change. Success Criteria: quality checks still
   green after the sweep.

2. **Verify pass** (risk: high) — confirm the work actually does what the plan
   called for. Two complementary checks, both required:
   - **Branch-wide deep review** — dispatch ONE `code-reviewer-deep` (omit
     `model`) over the assembled branch diff (`git diff <base>...HEAD`). The
     per-loop reviews were phase-scoped; this is the only fresh-eyes look at
     cross-phase interactions. Findings route through `/review`'s severity
     gating.
   - `/verify` — reconcile the shipped diff against the ticket/plan
     (completeness, every Acceptance Stub flipped), run the plan's Automated
     Verification commands, and emit the **human smoke-test checklist** (ACs
     + all human-only Manual Verification items).
     Success Criteria: deep review clean, reconciliation reports no missing
     work, smoke-test checklist delivered.

3. **Orient pass** (risk: low) — `/orient` to rebuild the mental map diff
   review misses: how the change connects to the unchanged code around it,
   what it now touches, what a reader needs to know next. Success Criteria:
   orientation summary produced; any surprise coupling surfaced as a
   follow-up.

4. **Recap** (risk: low) — `/branch-recap` reassembles the branch into one
   artifact before the PR: the **cross-phase test audit** (cull + coverage-net,
   the half of test-intent no phase can judge locally), `/stage` triage of the
   closing phases' own residue, and the recap receipt. It runs no gates — each
   already fired where its oracle was sharper. Success Criteria: recap
   produced; residue queue handed to the user.

Nothing after this is a phase. `/adr` is **post-PR** — it wants the PR link.

## Phase Status lines (copy verbatim, renumbering)

```markdown
- [ ] Phase N: Refactor pass — /refactor cleanup sweep (risk: low)
- [ ] Phase N+1: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase N+2: Orient pass — /orient situate the change (risk: low)
- [ ] Phase N+3: Recap — /branch-recap synthesis + residue triage (risk: low)
```
