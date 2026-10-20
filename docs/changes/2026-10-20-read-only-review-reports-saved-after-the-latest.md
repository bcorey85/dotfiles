---
type: "Change"
title: "Read only review reports saved after the latest review dispatch"
description: "The /code step machine read an old plan-impact review report again when a later review saved no report. It then asked the plan-change question again, started another review and added another Plan Deviations entry, in a loop that ended only when a reviewer handed back. after-review now reads only reports saved after the latest review dispatch, so a report is acted on once."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T08:51:12-05:00"}
seq: 2
components: ["script/code-step"]
evidence: ["path test"]
watches: []
---

## Change

`emit_review_dispatch` in `scripts/code-step.py` records how many rows `reports.jsonl` holds when it dispatches a review (state key `reviewReportsFloor`). `after-review` passes that count to `saved_messages`, which skips those rows. A review that saves no new report now takes the existing stop: "No review-loop packet was saved ... Tell the user."

A state saved before this change has no `reviewReportsFloor`, and reads from row 0 as before.

## Evidence

path test

`tests/scripts/test_code_step_termination.py` walks every step path breadth-first and fails on a path that returns to a state it already visited. It found the loop only at random, because each ruling carries a wall-clock minute stamp and the test hashed it into the state. With the minute masked, the test fails every time: 22 failing paths, 9 distinct loops. Each loop runs: a coder result, a review with a plan-impact report, the plan-change decision, then a review that saves no report. `after-review` matched the old plan-impact row by stage `review`, and `decide` did not consume it.

## Result

Against the patched script:

| Test | Before | After |
|---|---|---|
| Termination test, failing paths | 22 | 0 |
| `test_code_step.py` | | 66 pass |
| Full dotfiles suite | 448, 1 failure | 448 pass, 2 expected failures |

## Watch

None. The termination test runs in the dotfiles suite and fails if the loop comes back.

## Back-out

Restore `scripts/code-step.py` from the commit before this change. A state that holds `reviewReportsFloor` loads without error in the old script, which ignores the key.
