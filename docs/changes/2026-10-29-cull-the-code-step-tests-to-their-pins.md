---
type: "Change"
change_type: "removed"
title: "Cull the code-step tests to their pins"
description: "Deleted code-step tests whose behavior another test already pins, merged near-duplicates into subTest tables, and replaced slow end-to-end parse checks with unit tables; no script behavior changed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T08:52:25-05:00"}
seq: 243
kind: "fix"
components: []
evidence: ["census"]
watches: []
test: "tests/run.sh::full suite, 0 failed"
asked: ""
proof: []
unmeasured: ""
---

## Change

Tests only; no script changed. Before each deletion the coder opened the test said to pin the same behavior and
confirmed it asserts it; where it did not, the test stayed. No fails-before test exists because no behavior changed.

Cuts made:
- 1. Agent-mode review-loop tests in `test_code_step.py`: 13 tests deleted. The six that cover a review-loop resumed
  after the wait cap are replaced by one merged test (no-wait stop text, waiting with the first wait time saved once,
  the cap stop, waiting again after the cap, and the hand-back clearing the resume marks), which keeps the
  resumed-review pins. The remaining deleted tests are pinned by the script-mode review tests.
- 2. ALREADY-DONE line forms: one 22-row unit table on `already_done_ask_numbers`; the end-to-end tests stay.
- 3. Prohibitions: one 14-row table on `run_verification_commands`, plus a test of `is_search_ban` on a search
  inside a `test -n` wrapper; the two end-to-end tests stay.
- 4. Cargo: five tests deleted, two merged into one that now asserts the gate sets no cargo variable.
- 5. Python and Django gates: one 16-row table that reuses the existing `django_phase` helper.
- 9. Phase id and run-notes parsing: one `StartArgsTest` table over `split_quoted_flags`, `phase_words_as_flag`,
  `parse_start_args` and `carry_run_notes`; six end-to-end tests deleted, three kept.
- 10. hand_back question.md stops: one 6-row table; the two reviewer-question tests are one 2-row table.
- 11. Restart text, planless-restart asks and review-again per stop are tables.
- 12. Stale phase: the no-dispatch-time resume and the coder-edited-phase-text resume deleted (pinned by
  `test_code_step.py` and the review-loop-edit and inserted-above stale tests); the changed-phase and phase-left-plan
  tests are tables.
- 13. cap_reached, review_script and resume merges as listed.
- 14. asks: the `ITEM_KEYS` test deleted, the not-an-id tests one 4-row table; open_phase: the state-directory test
  deleted, the stop outcomes one 3-row table.

Cuts made in part:
- 6. Three plan-format tests deleted (pinned by `test_plan_format.py`) and three moved there. Kept
  `test_phase_section_lookup_keeps_six_and_six_a_apart` (the pin covers 6 versus 6.1, not 6 versus 6A) and the
  fenced status-line test (no plan_format test covers a status line in a fence).
- 7. One duplicate wait test deleted; the wait-cap, no-gate-variable, claude/yes and plan_check tests merged. Kept
  the planless conflicting-values test (its only pin) and the two restore-message start tests (different setups).
- 8. Two agent-mode tests deleted (pinned by review_script tests). Kept the review wait-cap question.md test (the
  script test asserts only the stop output), the no-message review-cap ask and the launch-id hand-back test (no
  script-mode test asserts either).

## Evidence

Census of test names against the tests that pin the same behavior. Full suite at the base, run alone: 3943 tests in
99 files, wall-clock 267.0s, sum of per-file seconds 1500.3s, 0 failed. After: 3762 tests in 99 files, wall-clock
236.8s, sum of per-file seconds 1084.9s, 0 failed. `test_code_step.py` went from 573 tests in 270.9s to 500 in
162.5s, and `test_code_step_review_script.py` from 170.7s to 128.8s. Merged cases still run as table rows.

## Result

181 fewer tests, 30s less wall-clock and 415s less summed test time, no failures.

## Watch

None; tests only.

## Back-out

Revert the test files in this change.
