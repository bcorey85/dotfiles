---
type: "Change"
change_type: "removed"
title: "delete the unreachable wait-for-loop path in review_fix.py"
description: "review_fix.py packet no longer prints wait-for-loop or keeps waits.json, and stop rows drop the open_dispatches and blocked fields that no writer set."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T09:58:35-06:00"}
seq: 3
kind: "fix"
components: ["script/review-fix", "script/handback", "script/review-loop-packet"]
evidence: ["delete-the-unreachable-wait-for-loop-path-in"]
watches: []
test: "tests/scripts/test_review_fix_script.py::test_an_old_stop_row_with_open_dispatches_and_no_hand_back_is_a_miss_not_a_wait"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_fix.py`: deleted `wait_for_loop`, `waited_on_stop` (waits.json), `WAIT_EXIT_CODE` and the `LoopWaitingError` branch of `packet`.
- `saved_handback.py`: deleted `LoopWaitingError`.
- `handback_store.py`: deleted `LOOP_WAITING` and `settled_stop`; any stop row is the standing stop.
- `handback.py`: deleted `stop_rows_after`, `settled_stop_row` and the waiting reason in `false_clean_reason`.
- `review_loop_packet.py`: the stop row carries `agent_id` and `ask_rows` only.
- Tests: the wait tests are gone. New tests show that an old stop row with `open_dispatches` above 0 reads as a miss, not a wait, and that its `ask_rows` still stand.

## Evidence

delete-the-unreachable-wait-for-loop-path-in. The only stop-row writer, `review_loop_packet.write_handback_rows`, always wrote `open_dispatches=0` and `blocked=False`, so the wait branch and the blocked skip never fired.

## Result

About 150 fewer lines in the review scripts and their tests. `packet` has one fewer exit code.

## Watch

—

## Back-out

Revert the commit.
