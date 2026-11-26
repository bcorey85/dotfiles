# Adopting a plan impact that needs only a ruling settles the review

Bug: a reviewer's PLAN-IMPACT that changes no acceptance criterion, held only because it cites a sign-off line the
user ruled, needs no code change when adopted: the code already holds, and the plan follows it through the
`## Plan Deviations` line `decide adopt` writes. `handback.adopt_settles` still requires every held impact to be
`applied` (coder edits in the tree), so `decide adopt` re-dispatches. The relaunch hands the pending adopted ruling to
the coder, which has nothing to change and skips it; the packet then stops on the NOT_APPLIED blocker and asks the
same plan-impact question again. The review never counts as clean.

Already shipped (not redone): a launch carries `--plan` (605b40b27), so the reviewer sees the Plan Deviations line;
`decide keep` exits for an adopted-unapplied ruling (1d7e1b9fc); fix/decide-adopt-launch-line is merged.
fix/review-fix-dead-plan-impact and fix/review-loop-delivered-plan-impact are stale and superseded.

## Scope

- In: `review/handback.py` (`adopt_settles` and a ruling-only helper beside it), `review/review_fix_plan_impacts.py`
  (`write_ruling_entry` records a settled adopt's rulings as applied; `APPLIED_ADOPT_LINE` wording),
  `review/review_fix.py` (the two decide paths pass the settle flag; no net line growth: the file is at the 1000-line
  cap), `tests/scripts/test_review_fix_script.py`.
- Out: `review/review_loop_scope_guard.py` (another lane owns it); impacts that change an acceptance criterion (they
  still re-dispatch); the packet's ask wording.

## Phase Status

- [x] Phase 1: a ruling-only adopt settles and leaves no pending adopted ruling (risk: medium)

## Phase 1: a ruling-only adopt settles and leaves no pending adopted ruling

1. `handback.py`: add `needs_only_ruling(impact)`: True when the impact changes no acceptance criterion
   (`not impact["ac_change"]`) and its cause is `plan`. `adopt_settles(packet, held)` returns True when every held
   impact is `applied` or `needs_only_ruling`, and the packet carries nothing (`carried_findings` empty). A None
   packet or an empty `held` still never settles. The state flag `plan_impact_adopt_settles`, set at packet time from
   the same function, follows with no change.
2. `review_fix_plan_impacts.write_ruling_entry`: a new keyword `applied=False`. When True, each ruled row it writes
   also gets a `handback_store.record_applied_ruling` with an `AdoptedRuling` of the same text, finding text, owner and
   ruled-at time, so `handback_store.rulings(...).adopted` (pending) no longer hands it to a later fix pass.
3. `review_fix.py`: `decide_from_hand_back` and `record_plan_ruling` compute whether the adopt settles before they
   call `write_ruling_entry`, and pass `applied=` that value. A keep passes nothing.
4. `APPLIED_ADOPT_LINE` names both cases: the held plan impact needs no code change past what is already in the tree.
   Callers and tests that read the old words are checked and updated.

#### Automated Verification

- A walk test in `tests/scripts/test_review_fix_script.py`, through the packet path and through the hand-back path:
  a held impact `{ac_change: False, cause: plan, applied: False}` with nothing carried, adopted with
  `decide adopt --plan <plan>`, prints `ACTION: done` and no redispatch; the plan file holds the ruling under
  `## Plan Deviations`; `handback.false_clean_reason` is None (the push check counts the review clean);
  `handback_store.rulings(...).adopted` is empty, so the next launch hands the coder no adopted ruling (no
  NOT_APPLIED blocker) and the impact text is among the ruled `impacts` (no repeat ask).
- The test fails on the tree before the change.
- Existing adopt tests (an `ac_change: True` impact still re-dispatches; carried findings still block) pass.
- `bash tests/lint.sh` on the changed files and `python3 tests/parallel_tests.py test_review_fix_script.py` pass.
- `bash tests/run.sh` passes.

## Plan Deviations

- 2026-11-26, session ruling (no acceptance criterion changed): a review plan impact observed that needs_only_ruling also settles reviewer-gate impacts held because they cite a user ruling, so no code fix is made for them; the plan's wider predicate (ac_change false and cause plan, any gate) is kept as the Bug text states it.
