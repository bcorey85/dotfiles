---
type: "Change"
change_type: "fixed"
title: "A review-loop dispatch from a lane subagent is refused"
description: "A review-loop that a subagent dispatched ended with no hand-back twice in a row; the dispatch gate now refuses it at once and names the main-session route, except from the /code fork."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T19:46:12-05:00"}
seq: 208
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::NestedDispatchTest::test_a_review_loop_dispatch_from_a_lane_subagent_is_refused_with_the_main_session_route"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_gate.py`: the Agent dispatch check refuses a review-loop dispatch whose hook event names a calling
  agent, unless that agent is the /code fork. The reason tells the caller to run /review from the main session. The
  `caller: code` handoff check is unchanged.
- `lib/script_utils.py` holds the /code fork's agent type, which the gate and `code_step_core.py` both read.

## Evidence

- A background lane agent ran /review twice. The first nested loop's first shell call was refused, since a
  non-interactive nested agent cannot ask for permission, and the loop stopped. The second dispatched its reviewer in
  the background and ended its turn waiting; the reviewer's report never woke it. Neither called SubagentHandback, so
  `review_fix.py packet` printed stop-no-handback both times. The hand-back hook's session keying was not the cause:
  no hand-back call was ever made.
- The /code fork dispatches review-loop on a resume, so it stays allowed.

## Result

- The new test fails before (no deny) and passes after. A second test keeps the main session and the /code fork
  allowed.

## Watch

—

## Back-out

Revert the commit.
