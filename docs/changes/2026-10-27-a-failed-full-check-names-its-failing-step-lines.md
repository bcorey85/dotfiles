---
type: "Change"
change_type: "changed"
title: "A failed full check names its failing step's lines"
description: "full_check puts the lint errors and FAIL lines in a failed check's blocker, calls a step that stops on a missing path a check-command error, and the check finder keeps a workflow's default working directory on every step."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:59:30-05:00"}
seq: 141
kind: "fix"
components: ["script/review-loop", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_full_check_that_fails_lint_names_the_lint_error_in_its_blocker"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `full_check.run` returns the failing step's lines on a failure: each ruff error with its ` --> file:line:col` line,
  and the FAIL, ERROR and FAILED lines. When the log holds none of them, it returns the log's last lines as before.
  The review loop's blocker carries those lines.
- A failed check whose last lines show a missing path (git's `ambiguous argument ... unknown revision or path`, a
  shell `cd` or script on a missing path) returns `not run (check-command error: <line>)` when that path did not
  exist at the diff base either (`--base`, HEAD by default; from the repo root or any folder below it). It is no
  failure, so no repair coder and no blocker, and the hand-back shows the line. A path the diff removed or moved
  stays a failure and goes to repair.
- The check finder's prompt says a workflow's or job's `defaults.run.working-directory` holds for every step without
  its own, and to write each such step as `(cd <dir> && <step>)`.
- The review-loop agent's Step 6 and packet line name the new result.

## Evidence

- A /code run stopped on "full check still failing after one repair" with only a passing test tail. The failure was
  an enforced C901 lint error printed before the tests.
- A composed full check ran a git freshness step from the repo root, outside the workflow's working directory. It
  failed on a missing path, and the loop stopped the phase on a critical blocker.
- The new tests fail on the old scripts.

## Result

- A failed full check's blocker names the failing lint error or test.
- A check-command fault no longer stops a phase as a code blocker.

## Watch

—

## Back-out

Revert the commit.
