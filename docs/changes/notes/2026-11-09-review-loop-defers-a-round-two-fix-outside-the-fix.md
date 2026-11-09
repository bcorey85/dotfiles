---
type: "Change"
change_type: "fixed"
title: "Review loop defers a round-two fix outside the fix diff"
description: "From round two on, `review_loop_script.py` sends a `fix` finding to the fix coder only when it touches the previous fix diff or its class is bug, correctness or security. Every other fix goes to the packet's `findings_remaining`, logged `actioned=none`. Those fixes alone start no further round, and a converged run that still holds one ends `deferred`. Round one is unchanged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-09T13:53:44-06:00"}
seq: 3
kind: "fix"
components: ["script/review-loop", "script/review-loop-fix-induced"]
evidence: ["tests", "telemetry"]
watches: ["review-loop-round-two-defers-outside-fix-diff"]
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_round_two_docs_fix_outside_the_fix_diff_is_deferred_not_sent_to_the_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review/review_loop_fix_induced.py`: `split_outside_fixes(out, iter, findings)` returns (sent, deferred). A finding is deferred when none of its parts is bug, correctness or security (`FIXED_OUTSIDE_FIX_DIFF`) and every part names a file:line outside the previous round's fix diff, with the `RANGE_SLACK` margin. A part with no file:line is sent. Round one, a missing diff file and an empty diff defer nothing. `fix_induced_tag` now matches a tail path (`deep/lib.py` for `pkg/deep/lib.py`) through `ranges_of_path`.
- `review/review_loop_script.py`: `defer_outside_fixes` runs after each review round. It moves the deferred findings to `open_fixes`, so they show up in `findings_remaining`, and drops them from `round_fixes`, so they are not marked fixed. `walk` turns a converged run that still holds a deferred finding into `deferred`.

## Evidence

The script documented a two-round bound, but round-two reviewers filed fixes on lines the fix step never touched. The script sent those to the coder, the edit went unreviewed, and /code ran another pass: 46 of 84 /code runs reached round 3.

## Result

Both new loop tests fail against the base script and pass with the change: `test_a_round_two_docs_fix_outside_the_fix_diff_is_deferred_not_sent_to_the_coder` (defer path) and `test_a_round_two_bug_fix_outside_the_fix_diff_still_goes_to_the_coder` (keep-bug path). Six `SplitOutsideFixesTest` unit tests in `tests/scripts/test_fix_induced.py` cover the split itself. Suite: `bash tests/run.sh` passes, 3313 tests in 124 files.

## Watch

`review-loop-round-two-defers-outside-fix-diff`: code-reviewer rounds past round two per /code review loop should fall.

## Back-out

Revert the commit.
