---
type: "Change"
title: "Review loop parsing, stop causes and crash handling"
description: "The review loop script reads its disposition, check-finder and closure replies from the last JSON object, not the first brace. A coder report that denies an /eng-spec recommendation no longer stops the run. A crashed review loop stops as a tool fault that review-again accepts, and an oversized fix diff is cut before it reaches a reviewer prompt."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T00:17:26-05:00"}
seq: 143
kind: "fix"
components: ["script/review-loop-script", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_disposition_reply_with_braces_in_its_prose_still_reads_the_findings_object"
asked: ""
proof: []
unmeasured: "A parsing, stop-text and crash-routing fix; the intake holds no number that reads it."
---

## Change

- `review_loop_script.py`: one `last_json_object(reply, keys)` helper reads the last JSON object that holds a wanted
  key. The disposition call, the check-finder call and the closure check use it, so braces in a reply's prose no
  longer break the read. The reviewer prompt cuts a round-one fix diff past `MAX_INLINE_FIX_DIFF_CHARS` at a line and
  points the reviewer at `git diff HEAD -- <file>` for the rest.
- `code_step.py`, `code_step_report.py`, `code_step_start.py`, `code_step_review.py`: the coder stops the run for
  /eng-spec only on a line that starts `RECOMMEND: /eng-spec`; the coder brief asks for that line. The stop text names
  its cause: the coder recommended /eng-spec, or it produced no reviewable change.
- `code_step_review.py`: a critical-blocker packet whose blocker is the loop script's own crash note stops with
  "the review did not run to the end", names it a tool fault, and sets stop reason `review-crashed`, which
  `review-again` accepts.
- `tests/scripts/test_code_step_termination.py`: a second walk covers the review loop as a detached script, with a
  stand-in that hands back each review outcome or is already gone.
- `tests/scripts/test_review_loop_script.py`: new tests for the skipped repair coder on a spec-file check failure, the
  test-only fix, the markdown-only fix, the SKIPPED coder line, nit locations, and the telemetry-off path.

## Evidence

Judgment. Each fix has a test; the disposition-brace test, the crashed-review test and the oversized-diff test were
run failing before the source edit. The /eng-spec marker tests and the coverage tests were written after the source
edit and pin its behavior without a recorded failing run.

## Result

The touched test files pass and ruff is clean on them. The script-mode walk stops at its node budget with no failing
path.

## Watch

—

## Back-out

Revert the branch commit. Nothing outside these scripts and their tests changes.
