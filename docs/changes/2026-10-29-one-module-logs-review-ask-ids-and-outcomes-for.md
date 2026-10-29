---
type: "Change"
title: "One module logs review ask ids and outcomes for /review and /code"
description: "A new review_asks.py fills ask ids and logs ask outcome rows for both /review and /code, so a plan-impact ask now gets no id and no outcome row in /code, as in /review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T11:26:26-05:00"}
seq: 257
kind: "fix"
components: ["skill/review", "skill/code"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_code_step_asks.py::LogAskOutcomes::test_a_plan_impact_ask_logs_no_outcome_row_as_review_does"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_asks.py` is the one place that fills ask finding ids (`supply_finding_ask_ids`) and logs one ask's
outcome row (`log_ask_outcome`, which returns the row's id, exit code, output and new-id note). It holds
`ASK_OUTCOMES`. Both skip a plan-impact ask. `review_fix.py` and `code_step_review.py` call it in place of their own
copies.

The pure helpers of /code's asks route (the ask listing, the pre-set outcome, the asks-done arguments, the asks coder
prompt and the prior issues) move from `code_step_review.py` to a new `code/code_step_asks.py`. `code_step_review.py`
drops from 1048 to 974 lines. The ruled-asks recording and the review-loop packet's ask parsing are not touched.

## Evidence

/code gave a plan-impact ask a finding id and logged an outcome row for it; /review logged neither. The same ask
logged two ways depending on the caller.

## Result

The new test failed before the change (/code logged a row for the plan-impact ask under a new id) and passes after it.
The /code and /review ask tests, retargeted at the shared module, pass unchanged in what they assert.

## Watch

None; a fix with a test.

## Back-out

Revert `review_asks.py`, `code_step_asks.py`, the call sites in `review_fix.py`, `code_step_review.py` and
`code_step.py`, and the test edits.
