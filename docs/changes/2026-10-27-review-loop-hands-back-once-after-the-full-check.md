---
type: "Change"
title: "review-loop hands back once, after the full check"
description: "The hand-back hook denies a review-loop report with no full check after its last code change, and denies a second report from an agent whose first was delivered; the stop gate no longer sends a delivered loop back to work."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T21:45:52-05:00"}
seq: 135
kind: "fix"
components: ["script/handback", "script/review-loop-gate", "script/open-child-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_second_hand_back_from_an_agent_with_a_stored_report_is_denied_and_adds_no_row"
asked: ""
proof: []
unmeasured: ""
---

## Change

The full-check gate moved from the SubagentStop backstop to the PreToolUse SubagentHandback hook. A review-loop hand-back whose transcript shows a coder step after the last full check is denied with the stop gate's reason, unless the packet names a plan impact or the repo's CLAUDE.md says `Full suite: CI` (both gates share `review_loop_gate.full_suite_in_ci`). The denial is recorded with the last code step it saw and repeats only after a later code change, so a loop cannot be trapped. A transcript the hook cannot read never blocks.

A second hand-back from an agent that already has a recorded `handback` row is denied and records nothing; the reason says to use SendMessage and stop.

The stop backstop skips the full-check reason once a hand-back was delivered, and keeps it for a loop that stops without one. `own_transcript_path` moved from open_child_gate.py to `script_utils.agent_transcript_path`. `handle_dispatch` split out of `handle_hook` to keep it under C901 10.

Two test_code_step.py tests from the blocked-stop change modelled a loop that hands back a second packet after a blocked stop. That second hand-back is now denied, so they check that the later unblocked stop marks the phase done with the one delivered packet.

Also in this commit: a test in test_review_fix_script.py that failed when the random temp dir name held "ops" now checks row values, not the dumped JSON.

## Evidence

Judgment from one /review run on 2026-10-27. The loop handed back converged before the full suite, the stop gate sent it back to work, it dispatched a coder and handed back again. The harness refused that second report, but the hook had already recorded it, so `review_fix.py packet` read a second packet and logged its asks twice.

## Result

Tests in test_handback.py cover: denied with a code change after the last full check (clean and cap-reached), passed with a plan impact or after a full check, a repeat on the same state passes, a new code change is denied again, an unreadable transcript passes, and a second report is denied with no row. test_review_loop_gate.py covers the stop gate after a delivered hand-back.

## Watch

None: a hook contract with unit tests.

## Back-out

Revert the commit.
