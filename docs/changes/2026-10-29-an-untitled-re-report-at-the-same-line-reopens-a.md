---
type: "Change"
title: "An untitled re-report at the same line reopens a titled fixed finding"
description: "When a plan-change round re-reported a fixed finding without a title, the loop matched it only against untitled fixed findings, so a titled finding at the same file and line stayed in fixed while its re-report stayed open. Two findings now match on a near title only when both have a title, and on the same file and line otherwise."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T02:20:54-05:00"}
seq: 226
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_an_untitled_fix_at_the_same_line_reopens_a_titled_fixed_part"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_findings.py`: new `same_finding` decides whether a fixed finding and an open fix name the same issue. In the same file, it compares titles when both have one, and lines otherwise. `unreported_parts` uses it, so an untitled re-report at a titled fixed finding's file and line takes that finding out of `fixed` and leaves it open.

## Evidence

- Failing first: on the base commit, `test_an_untitled_fix_at_the_same_line_reopens_a_titled_fixed_part` fails, because the titled part stays in `fixed`.

## Result

- `test_review_loop_script.py` passes, and ruff is clean.

## Watch

—

## Back-out

Revert the commit.
