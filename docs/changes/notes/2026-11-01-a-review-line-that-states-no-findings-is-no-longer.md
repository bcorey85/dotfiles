---
type: "Change"
change_type: "fixed"
title: "A review line that states no findings is no longer an ask, and a clean prose hit is no longer a skipped finding"
description: "The review record stops counting clean passes as asks and skipped findings, so false-positive and ask counts read true."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T19:15:23-06:00"}
seq: 456
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_reviewer_line_that_states_no_findings_is_not_an_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_loop_findings.py` treats a reviewer line that states no findings as no finding. The stale-prose pass in `review_loop_script.py` no longer records a skip when the claims it checked hold.

## Evidence

Bench review loops logged clean reviewer lines as asks, and logged a prose check whose claims held as a skipped false positive.

## Result

Both tests fail on the old code and pass on the new. The full suite passes: 3034 tests, 0 failed.

## Watch

None. Skip counts in new work logs drop for this reason, not because reviewers got more accurate.

## Back-out

Revert the branch merge.
