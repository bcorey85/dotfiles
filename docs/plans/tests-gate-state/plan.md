# Tests keep out of the real review-gate state

Fix the queued defect `toolkit-tests-write-review-gate-records-into-the`: test runs wrote session and reviewed-tree
rows into the live `~/.claude/state/review-gate`. Tests live in `tests/scripts/`, paths from
`tests/scripts/toolkit_paths.py`.

## Scope

- In: a shared helper `tests/scripts/isolated_state.py` that points HOME at a temp folder, its use in `test_handback.py`
  and `test_review_fix_script.py`, the test files that reached the review-gate state with the real HOME,
  `tests/review_gate_unchanged.py` run around the tests by `tests/run.sh`, their tests, and one change note in
  `docs/changes/notes/`.
- Out: the live state files already in `~/.claude/state/review-gate` (no cleanup from this branch).

## Phase Status

- [x] Phase 1: tests isolate the state root; the suite checks the real gate folder for test rows (risk: low)

## Phase 1: tests isolate the state root; the suite checks the real gate folder for test rows

**Files**: `tests/scripts/isolated_state.py`, `tests/scripts/test_handback.py`, `tests/scripts/test_review_fix_script.py`,
`tests/review_gate_unchanged.py`, `tests/run.sh`, `tests/scripts/test_run_sh.py`
**Test**: `tests/scripts/test_isolated_state.py`, `tests/scripts/test_review_gate_unchanged.py`

## Automated Verification

- `bash tests/run.sh`

## Plan Deviations

- AC2 checks only new repo keys under the run's temp folder, by content, not the listing. Ruled by agent-evals-5e on
  2026-11-13. Reason: live sessions and other suite runs add their own keys to the same files while a run is open, so
  a listing check, or a check of every new key, fails while another lane is active. Signed off by the user (Brandon
  Corey, 2026-11-13 11:32 and 11:48; see the adopt entries below).

- 2026-11-13: Adopt plan change. Ruled by Brandon Corey at 2026-11-13 11:32.

  The ruling: AC2 reword accepted (Brandon, 2026-11-13)

  The disagreement:
  PLAN-IMPACT:
    assumed: AC2 can be narrowed to "no new repo key under the run's temp folder", on the session ruling alone.
    found: `plan_check.py owner` returns `plan`. That rule says a cut that drops what the ticket's text asks for needs the user. The ticket asks for "unchanged, checked by listing before and after".
    changes: The `## Plan Deviations` line needs the user's sign-off, with who and when. Options: (a) the user accepts the reword and I record it, or (b) AC2 goes back to the ticket's wording and the test is reworked.
    acceptance_criteria: AC2
    cause: plan

- 2026-11-13: Adopt plan change. Ruled by Brandon Corey at 2026-11-13 11:48.

  The ruling: AC2 reword accepted (Brandon, 2026-11-13)

  The disagreement:
  PLAN-IMPACT:
    assumed: the plan's reworded AC2 (no new repo key under the run's temp folder) stands in for the ticket's "full suite run leaves the real review-gate folder unchanged, checked by listing before and after".
    found: docs/plans/tests-gate-state/acceptance-criteria.md:4 and docs/plans/tests-gate-state/plan.md:33-34. The reword has only a session ruling. `plan_check.py owner` returns `plan`, so a cut that drops what the ticket asks for needs the user.
    changes: the `## Plan Deviations` line needs the user's sign-off with who and when. Options: (a) the user accepts the reworded AC2 and gives the wording of the sign-off; (b) the user rejects it, and AC2 goes back to the ticket's "unchanged, checked by listing" with the test code changed to match.
    acceptance_criteria: AC2
    cause: plan
