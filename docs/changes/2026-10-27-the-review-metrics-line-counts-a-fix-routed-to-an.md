---
type: "Change"
title: "The review metrics line counts a fix routed to an ask under ask"
description: "A [design-decision] fix that the review loop sends to the user as an ask now counts under ask on the metrics line, not under fix, in the scripted loop and in the review-loop agent's Step 7 rule."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T14:30:59-05:00"}
seq: 108
kind: "fix"
components: ["script/review-loop-script", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_design_decision_fix_counts_as_an_ask_in_the_metrics_row"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_script.py` splits off the `[design-decision]` fixes before it tallies a review: they count under `ask`,
  and `fix` and `blocker` no longer count a `[design-decision]` fix.
- `review-loop.md` Step 7 (and the opencode port) says a `fix` finding routed to `ask[]` counts under `ask`, not `fix`.

## Evidence

- A /code run's metrics line said fix=10 while 9 were fixed: the tenth fix went to the user as an ask, and the line
  counted it under fix, not ask.
- The new test gives one plain fix and one `[design-decision]` fix. Before the change the row read fix=2 ask=0 fixed=1;
  now it reads fix=1 ask=1 fixed=1.

## Result

- Every ask the user sees, including a `[design-decision]` fix, is counted in `ask`; `fix` and `blocker` no longer count a `[design-decision]` fix.

## Watch

—

## Back-out

Revert the commit.
