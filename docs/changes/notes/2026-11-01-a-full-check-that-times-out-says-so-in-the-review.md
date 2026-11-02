---
type: "Change"
change_type: "fixed"
title: "A full check that times out says so in the review packet"
description: "A timed-out full check now puts a note in the packet's tool_fault, so a phase can no longer finish with no full check and only a label to show it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T19:28:17-06:00"}
seq: 457
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_packet_whose_full_check_timed_out_carries_a_tool_fault_naming_the_faster_command_fix"
asked: ""
proof: []
unmeasured: ""
---

## Change

`full_check.py` gains `TIMEOUT_NOTE` and `fault_note(result)`, and prints the note on a timeout. `review_loop_script.py` puts the note in the packet's `tool_fault`. The note says the check did not finish and names the fix: a faster `Quality check (<repo name>): <cmd>` entry in `~/.claude/CLAUDE.local.md`. The run stays non-blocking.

## Evidence

Full-check discovery runs whole repo checks on repos that had none, so timeouts become likely. The scripted loop's limit is 900 seconds and the agent-run path's default is 540.

## Result

The new test fails on the old code and passes on the new. See the suite count in the branch report.

## Watch

None.

## Back-out

Revert the branch merge.
