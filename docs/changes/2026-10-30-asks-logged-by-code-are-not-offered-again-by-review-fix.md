---
type: "Change"
change_type: "fixed"
title: "asks that a /code run logged are not offered again by review_fix.py packet"
description: "code_step_review writes the same asks-logged row as review_fix asks-done, through one writer in handback_store."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T15:00:00-05:00"}
seq: 310
kind: "fix"
components: ["script/code-step", "script/review-fix", "script/handback"]
evidence: ["review-finding"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_asks_logged_by_code_are_not_offered_again_by_review_fix_packet"
asked: ""
proof: []
unmeasured: "No intake row counts asks offered again after a /code run logged them."
---

## Change

`handback_store` now owns the asks-logged row: `ASKS_LOGGED_ROW`, `record_asks_logged(session_id, packet_id, repo)`, `repo_that_logged_the_asks(session_id, packet_id)`, and `hand_back_id`, moved from `saved_handback`, plus `agent_hand_back_id(session_id, agent_id)`. `review_fix.py` calls the store's writer and reader.

`code_step_review.command_after_review` saves the review-loop's hand-back id as `asksPacketId` when the packet holds asks. `log_ask_outcomes` then writes the asks-logged row for it, so asks-done, a pre-set outcome and a corrected ruling all record it. Before, only `review_fix.py asks-done` wrote the row, so `review_fix.py packet` offered a /code run's logged asks again.

## Evidence

The review of seq 309 named the `/code` asks-done path as writing no asks-logged row.

## Result

One test fails without the change: `review_fix.py packet` after a /code asks-done prints `ACTION: done` with the /code repo and logs nothing. A second test, a pointer ask repeated in a later review round giving one DROPPED ASKS line, is a regression guard that already passes at base.

## Watch

None: no intake number counts either shape.

## Back-out

Remove `record_run_asks_logged` and its call at the end of `log_ask_outcomes` from `code_step_review.py`, and the `asksPacketId` save; move the asks-logged functions back into `review_fix.py` and `hand_back_id` back into `saved_handback.py`; drop `agent_hand_back_id`; revert the two tests.
