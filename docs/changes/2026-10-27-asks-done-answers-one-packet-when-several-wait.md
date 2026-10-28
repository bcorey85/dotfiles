---
type: "Change"
title: "asks-done answers one packet when several wait"
description: "A second packet no longer replaces the first packet's unanswered asks; asks-done takes --packet to pick which packet it answers."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T17:31:35-05:00"}
seq: 115
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_second_packet_keeps_the_first_packets_unanswered_asks_and_asks_done_names_the_packet"
asked: ""
proof: []
unmeasured: ""
---

## Change

The state file held one packet, so a second review-loop hand-back before the user answered the first packet's asks started a fresh state and lost those asks. A different packet now keeps the previous packet's state under waiting_packets when that packet still has unanswered asks. asks-done works as before with one packet waiting; with several it refuses, lists each (packet id, ask count, first ask) and takes --packet to pick one. The present-asks line names --packet when another packet waits. The "already logged" reply fires only when no packet holds unanswered asks. A packet that fails to parse no longer cancels the previous packet's unanswered asks: the next good packet keeps them.

## Evidence

Judgment from reading the script. The test hands back a one-ask and a two-ask packet before any answer, checks the refusal lists both, and checks each --packet call logs its own packet's rows with its own finding ids.

## Result

Both packets' asks can be answered and logged, one packet per asks-done call.

## Watch

None: a script path with a unit test.

## Back-out

Revert the commit.
