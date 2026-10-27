---
type: "Change"
title: "review packet waits on a shell the loop moved to the background"
description: "The review-loop stop gate counts a shell call moved to the background, by run_in_background or its timeout, as open work until its task notification, so packet prints wait-for-loop, not stop-no-handback."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T11:08:03-05:00"}
seq: 4
kind: "fix"
components: ["script/review-loop-gate", "script/review-fix", "script/handback", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_loop_that_stops_on_a_shell_its_timeout_moved_to_the_background_gets_wait_for_loop"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_gate.py` reads each shell result record whose `toolUseResult` names a `backgroundTaskId`. That call
  stays open until a task notification names its tool-use id. The stop row's `open_dispatches` count adds the open
  shells, so the stop passes and `hand_back_gap` returns LOOP_WAITING.
- The wait text in `review_fix.py`, `handback.py` and the /review and /fix skills names "an agent or shell" in place of
  "an agent it launched".
- Two fixtures copy real records: a full suite moved to the background by its 600 s timeout (notified by a user
  message) and a `run_in_background` call (notified by an attachment).

## Evidence

- Queue item `review-fix-packet-says-stop-no-handback-while`: a /review session got `stop-no-handback` while its
  review-loop still waited on a suite its timeout had moved to the background. The packet said to re-dispatch a second
  loop over the same files.
- Over 1040 real review-loop transcripts, the gate parsed 1040. 13 end with an open background shell; 11 of those have
  no other open work, so the old gate stored 0 for them.
- The new tests fail on the base commit (`[0, 0] != [1, 0]`; packet exits 2 with `stop-no-handback`) and pass after.

## Result

- `test_review_loop_gate`, `test_review_fix_script` and `test_handback` pass (288 tests); ruff passes.
- A shell stopped with TaskStop and never notified stays open. Packet then prints wait-for-loop once and `stop` on the
  next call.

## Watch

—

## Back-out

Revert the commit.
