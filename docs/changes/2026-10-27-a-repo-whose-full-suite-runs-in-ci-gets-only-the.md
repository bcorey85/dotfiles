---
type: "Change"
title: "A repo whose full suite runs in CI gets only the changed-file tests in review"
description: "A repo whose CLAUDE.md holds the line `Full suite: CI` skips the review loop's full check and runs the changed files' tests, and a full check past its time limit reports `not run (timeout)` with its process group killed, never a critical blocker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T20:39:42-05:00"}
seq: 127
kind: "fix"
components: ["agent/review-loop", "script/review-loop-gate", "script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_full_check.py::FullCheckTest::test_a_check_past_its_limit_is_not_run_and_leaves_no_process_behind"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `review/full_check.py` runs the review loop's one full check. It prints `full check: passed`,
  `failed (exit N)`, `not run (timeout)` or `not run (CI)`.
- `full_check.full_suite_runs_in_ci` is the one reader of the exact CLAUDE.md line `Full suite: CI`, bare or as a list
  item. With the line present, the check does not run.
- A check past its limit (540 s from the CLI, 900 s in the scripted loop) is killed with its whole process group and
  reports `not run (timeout)`. That is no failure in any repo.
- review-loop Step 6 runs the check through `full_check.py` and copies the result into the packet's new `full_check`
  field. On `not run (CI)` it runs the changed files' tests by name. On `not run (timeout)` it goes on with no finding.
- review_loop_gate lets a loop stop in a `Full suite: CI` repo with no full check. It counts a `full_check.py` call
  whose command is unscoped as a full check.
- review_loop_script skips the check finder and the check in a `Full suite: CI` repo. Its coder calls already run the
  changed files' tests. A timeout no longer crashes the run into `critical-blocker`.
- The hand-back prints `Full check: not run (CI)` or `Full check: not run (timeout)`.

## Evidence

- A reported /code run hit the full-suite timeout in a repo whose full suite runs in CI. The loop stopped /code as a
  critical blocker, and the timed-out test processes stayed alive.
- The new tests cover the line present, absent and misspelled in full_check, the gate and the scripted loop, the
  timeout kill of a grandchild process, and the hand-back line. They fail on the old scripts.

## Result

- A repo can hand its full suite to CI, and a slow suite no longer stops /code.

## Watch

—

## Back-out

Revert the commit.
