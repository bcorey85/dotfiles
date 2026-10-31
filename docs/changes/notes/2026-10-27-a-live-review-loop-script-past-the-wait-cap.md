---
type: "Change"
change_type: "fixed"
title: "A live review loop script past the wait cap keeps the wait going"
description: "/code counts a running review loop script's wait cap from its last calls.jsonl or full-check.log write, and its cap stop says the script is still running, not that it died."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:59:00-05:00"}
seq: 136
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_review_script.py::ReviewScriptTest::test_a_running_script_with_progress_past_the_cap_keeps_the_wait_going"
asked: "2026-10-27: agent-evals-64 assigned queue item code-step-stops-a-live-review-loop-at-its-wait-cap"
proof: []
unmeasured: ""
---

## Change

- `code_step_core.cap_clock_start`: while the review loop script runs, the cap counts from the newest write to its
  `calls.jsonl` or `full-check.log` when that is later than the dispatch clock.
- `wait_for_handback` checks progress again at the end of the wait, so a write during the wait moves the cap past it.
- `stop_at_wait_cap`: when the script is still running, the stop names its pid and says it wrote no progress file in
  that time. "It may have died or been stopped" stays for a review-loop agent or a script that is gone.

## Evidence

- A /code run stopped with "It may have died or been stopped" while the loop script was alive and working: the cap
  counted from the loop's start.
- Both new tests fail on the old script.

## Result

- A running script with a recent progress write past the cap gets a wait, not a stop. A running script with no
  progress inside the cap stops without the word "died".

## Watch

—

## Back-out

Revert the commit.
