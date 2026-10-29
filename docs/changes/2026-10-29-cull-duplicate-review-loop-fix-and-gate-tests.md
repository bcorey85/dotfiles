---
type: "Change"
change_type: "removed"
title: "Cull duplicate review-loop, fix and gate tests"
description: "The review-loop, fix and gate tests lose duplicate runs and near-copies: like cases become subTest tables, and tests another test already pins are deleted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T07:59:10-05:00"}
seq: 242
kind: "fix"
components: ["script/review-loop-gate", "script/review-fix", "script/review-commit-gate", "script/review-loop-script", "script/code-step", "script/deferred-push-check", "script/handback", "script/open-child-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::LedgerRowsTest::test_a_missing_metrics_line_is_blocked"
asked: ""
proof: []
unmeasured: ""
---

## Change

Tests only; no script changes. Every cut below is made; none is skipped.

1. `test_review_loop_gate.py`: `LedgerRowsTest` no longer subclasses `ReviewLoopGateTest`. Both use a `StopHookMixin`
   that holds `stop()`, so the 16 inherited tests no longer run twice.
2. `test_review_fix_script.py`: the 18 parse-failure tests are one table, `test_a_malformed_packet_is_a_parse_failure`.
3. `test_review_commit_gate.py`: the 13 dirty-denied, clean-silent tests are one table. The read-only-git lists are
   merged, and four tests are deleted. The test with a folder option emptied by a heredoc message stays, because
   it is the only pin on that case.
4. `test_review_loop_script.py`: the 7 unreported-parts tests are one table, and the 3 plan-change ask tests are one.
5. `test_review_fixes.py`: deleted `OpenErrorLineTest`, the plain-space word-split test and the mid-line amend test.
6. `test_fixes.py`: deleted 2 tests and merged the decide-without-ruling test into `test_code_step.py`. The
   expectedFailure tests stay.
7. `test_review_fix_script.py`: the 3 decide usage tests are one table, and the 2 status-parse checks are one test.
8. `test_deferred_push_check.py`: the hidden and kept deferral cases are one table of 10 rows.
9. `test_review_loop_gate.py`: deleted the open-background-dispatch test, folded the non-object transcript line into
   the unreadable-transcript test, tabled the count tests, and folded the two flag-value scope tests into the
   scoped table.
10. `test_handback.py`: the cap-reached full-check denial is a row of the clean-denial test, not a deletion,
    because it is that case's only pin. The other-agents-not-stored test is folded into the review-loop store test.
    `test_open_child_gate.py`: deleted the open-background-child denial, which two denial tests repeat.

## Evidence

- A read-only cull audit of `tests/scripts` named each cut and what still pins it. Each pin was checked before its
  test went: the open-error line is asserted in four logger tests; the plain-space split by
  `test_spec_budget_gate.py`, whose `words()` joins with plain spaces; the mid-line amend by
  `test_git_discipline_gate.py`; the commit-gate deny text by `assert_commit_denied`'s full-constant compare.

## Result

- Full suite on the same base, before: 3928 tests, 261.5 s wall-clock, 0 failed. After: 3841 tests, 247.1 s, 0 failed
  (87 fewer runs).
- After merging the newer integration branch, which adds 15 tests: 3856 tests in 99 files, 223.2 s, 0 failed.
- The named test ran twice before (once per class) and runs once after.

## Watch

—

## Back-out

Revert the commit.
