---
type: "Change"
change_type: "fixed"
title: "A stop-status packet keeps its asks for asks-done"
description: "A cap-reached or critical-blocker packet that carries ask[] entries now prints and saves them, so asks-done logs their outcomes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T17:31:35-05:00"}
seq: 114
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_cap_reached_packet_with_asks_prints_them_and_asks_done_logs_their_outcomes"
asked: ""
proof: []
unmeasured: ""
---

## Change

A packet with status cap-reached or critical-blocker went to the stop path, which printed only the blockers or remaining findings. Its ask entries were neither shown nor saved, so asks-done refused with "no asks are waiting" and the answered asks stayed open in the findings log. The stop path now fills the ask ids, saves the asks with stage asks, and prints each ask and the asks-done line after the stop instruction. The ask listing is shared with the present-asks path. The gate-mark line is not printed on a stop status, since the gate stays dirty.

## Evidence

Judgment from reading the script: the stop path returned before the ask handling. The test runs a cap-reached packet with two asks through packet and then asks-done, and checks both outcome rows carry their finding ids. A second test does the same for critical-blocker.

## Result

asks-done after a stop-status packet logs one outcome row per ask.

## Watch

None: a script path with a unit test.

## Back-out

Revert the commit.
