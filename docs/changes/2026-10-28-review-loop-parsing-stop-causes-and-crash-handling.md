---
type: "Change"
title: "Review loop parsing, stop causes and crash handling"
description: "The review loop script reads its disposition and check-finder replies from the last JSON object that holds the wanted key, not the first brace. A coder stop names its cause: no reviewable change, or a recommendation of /eng-spec. The termination walk also covers the review loop run as a detached script."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T00:17:26-05:00"}
seq: 143
kind: "fix"
components: ["script/review-loop-script", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_disposition_reply_with_braces_in_its_prose_still_reads_the_findings_object"
asked: ""
proof: []
unmeasured: "A parsing, stop-text and test-coverage fix; the intake holds no number that reads it."
---

## Change

- `review_loop_script.py`: one `last_json_object(reply, keys)` helper reads the last JSON object that holds a wanted
  key. The disposition call, the check-finder call and the closure check use it, so braces in a reply's prose no
  longer break the read.
- `code_step.py`: `unreviewable_outcome` returns `no-change` or `recommended-eng-spec` in place of one `stop`, and the
  stop text names the cause that fired.
- `tests/scripts/test_code_step_termination.py`: a second walk covers the review loop as a detached script, with a
  stand-in that hands back each review outcome or is already gone.
- `tests/scripts/test_review_loop_script.py`: new tests for the skipped repair coder on a spec-file check failure, the
  test-only fix, the markdown-only fix, the SKIPPED coder line, nit locations, and the telemetry-off path.

## Evidence

Judgment. The disposition-brace test failed before the source edit. The stop-cause and coverage tests were written
after the source edit and pin its behavior without a recorded failing run.

## Result

The touched test files pass. The script-mode walk stops at its node budget with no failing path.

## Watch

—

## Back-out

Revert the merge commit that brings this branch in.
