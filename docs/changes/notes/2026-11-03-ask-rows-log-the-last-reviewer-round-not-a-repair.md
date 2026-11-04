---
type: "Change"
change_type: "fixed"
title: "Ask rows log the last reviewer round, not a repair-pass iter"
description: "Ask and ask-outcome rows from /code and /review carry the last round a reviewer ran in, so a closure or stale-prose repair no longer reads as an over-cap round 3."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T18:56:05-06:00"}
seq: 4
kind: "fix"
components: ["script/review-loop-script", "script/handback", "script/review-fix"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_handback.py::AskRowRoundTest::test_an_ask_row_carries_the_last_reviewer_round_not_a_repair_pass_iter"
asked: ""
proof: []
unmeasured: "Round-3 census rows are rare; the fix removes a miscount rather than moving a rate."
---

## Change

`review_loop_script.py` keeps `last_review_round`, set only in `review_round()`, and the outcome carries it as `review_round`. `review_loop_packet.py` writes it to the packet. `handback.py` reads it (`SCRIPT_PACKET_KEYS`, `INTEGER_KEYS`); a packet without it reads its `iter` as the round. `review_fix.py` stores it in state, and `handback.ask_row_fields` logs `iter=<review_round>`; a state saved before the field logs its `iter`.

## Evidence

A closure repair or stale-prose repair calls `next_round()` after the last reviewer, so the packet's `iter` reads 3 with only two reviewer rounds. The `disposition=ask` rows took that `iter`, and round-3 censuses counted them as over-cap reviewer rounds.

## Result

`AskRowRoundTest` (3 tests) failed before the change (`review_round` absent) and passes after. The stale-prose loop test now asserts `iter` 3 and `review_round` 2.

## Watch

None.

## Back-out

Remove `last_review_round`, the `review_round` packet key and state field, and restore `iter={context["iter"]}` in `ask_row_fields`.
