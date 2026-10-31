---
type: "Change"
change_type: "fixed"
title: "The review loop retries one unparseable disposition reply"
description: "When the sonnet call that sorts a reviewer's output into fix, ask and nit replies with no such object, the review loop now asks once more with the parse error and a request for the JSON object only. Before, the first bad reply stopped the loop as a tool fault after the reviewers had already spent about 860k tokens, and the only way on was a full rerun. A second bad reply still raises."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-30T05:29:27-05:00"}
seq: 325
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_bad_disposition_reply_then_a_good_one_retries_once_and_returns_the_findings"
asked: ""
proof: []
unmeasured: "No edit-watch entry yet; the retry is countable from the per-run calls.jsonl, which the intake does not read."
---

## Change

- `disposition_call` in `review_loop_script.py`: on a reply with no `{"fix", "ask", "nit"}` object it calls sonnet once more with the same prompt plus a note that the last reply could not be parsed, the parse error cut to its first 200 characters, and a request to reply with the JSON object only.
- The retry call has the role `disposition-retry`, so it gets its own row in the run's `calls.jsonl` and its own `call-NN-disposition-retry.json` file.
- A second unparseable reply raises the same `ValueError` as before, so it is still a tool fault.

## Evidence

- A loop stopped on one unparseable disposition reply after the reviewers spent about 860k tokens; nothing else recovered the work except a full rerun.

## Result

- `tests/scripts/test_review_loop_script.py`: bad then good makes two calls, returns the findings, and the second prompt carries the error capped at 200 characters; bad then bad raises `ValueError`; the retry is logged under `disposition-retry`; a full loop run with one bad reply then a good one converges.

## Watch

Every retry writes one row with `"role": "disposition-retry"` to the run's `calls.jsonl`. An intake that counts those rows per run gives the retry rate; a `ValueError` stop after a retry shows as a run whose last `calls.jsonl` row is `disposition-retry` and whose loop ended on the "holds no ... object" tool fault.

## Back-out

Revert the commit. The first unparseable disposition reply raises at once again.
