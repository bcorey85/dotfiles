---
type: "Change"
change_type: "fixed"
title: "A review-loop that ends on a packet with no hand-back call still hands back"
description: "The review-loop SubagentStop gate runs the hand-back hook on a final message that parses as a packet, so a loop resumed by SendMessage that returns its packet as text is stored, not reported as stop-no-handback."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T19:27:19-06:00"}
seq: 6
kind: "fix"
components: ["script/review-loop-gate"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::FinalTextHandBackTest::test_a_final_text_packet_is_stored_as_the_hand_back"
asked: ""
proof: []
unmeasured: "One work-machine incident; no intake number counts loops that end on a text packet."
---

## Change

`review_loop_gate.check_stop` gains one step. When a review-loop stop has no delivered SubagentHandback, no open background dispatch and no other block, and its final message parses as a packet, the gate calls `handback_hook.handle_hook` on that message. When the hook's gates pass, the packet is stored as the hand-back, and `review_fix.py packet` reads it as usual. When a gate denies, its reason blocks the stop, so the loop goes on and hands back. A denied `stop_hook_active` stop stores nothing and is not blocked. An error in this step goes to stderr and never blocks (fail-open). No prompt changed.

Stale hand-backs: the stored text is this stop's own final message from this agent. A hand-back already stored for the agent returns ALREADY_DELIVERED and adds no row. The store's dispatch reset is unchanged.

## Evidence

A review-loop hit a spend-limit stop and was resumed with SendMessage. It returned its packet as its final message, with no SubagentHandback call. `review_fix.py packet` found no stored hand-back, printed stop-no-handback, and the round was lost. On this machine a spend-limit-resumed loop that did call SubagentHandback was stored normally, so the gap is the text-only ending.

## Result

Five tests in `FinalTextHandBackTest`. Before the fix, three failed: the text packet was not stored, the unreviewed packet was not blocked, and an earlier dispatch's hand-back stood as the latest. After the fix all 108 tests in the file pass. SubagentStop median wall time over 30 runs, on a stop that ends on a packet: 108.0 ms before, 153.2 ms after (bare Python start 12.4 ms). The extra time is the hand-back hook's import and gates, paid only when the final message parses as a packet; other stops and the PreToolUse paths keep the old cost.

## Watch

None.

## Back-out

Remove `final_text_hand_back_reasons` and its call in `check_stop`, and the docstring paragraph that names it.
