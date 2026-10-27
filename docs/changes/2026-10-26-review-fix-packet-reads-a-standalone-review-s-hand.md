---
type: "Change"
title: "review-fix packet reads a standalone review's hand-back while a code run waits on another agent"
description: "review_fix packet refuses a hand-back only when it belongs to the agent the open /code run launched, so a standalone /review in the same session gets its fix packet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:40:05-05:00"}
seq: 78
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_standalone_review_hand_back_is_read_while_a_code_run_waits_on_another_agent; tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_code_run_hand_back_after_a_standalone_review_is_still_refused"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `active_code_step` takes the stored hand-back's agent id. The open /code run owns the hand-back only when that agent
  is among the run's logged launches; otherwise (a different agent, or no launch logged yet) `packet` reads it as a
  standalone review's. An earlier review-loop hand-back stays refused after a later coder launch.
- `saved_hand_back` reads the latest hand-back first, so the check compares against the hand-back it will return.
- A hand-back from the agent the /code run launched is still refused, as before.

## Evidence

- A session ran a standalone /review while a /code run in the same session sat at its review stage; `packet` refused
  the standalone review's hand-back and the fix step had no packet.
- Both named tests fail on the base script and pass after; two of the five new tests pin refusals that are unchanged: `test_hand_back_of_the_agent_the_code_run_launched_is_still_refused` and `test_earlier_review_loop_hand_back_after_a_later_coder_launch_is_still_refused`.

## Result

- See the branch's suite run. A /code run with no launch record owns no hand-back.

## Watch

—

## Back-out

Revert the commit.
