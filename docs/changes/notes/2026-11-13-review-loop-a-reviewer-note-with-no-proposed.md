---
type: "Change"
change_type: "fixed"
title: "Review loop: a reviewer note with no proposed change is no ask, repeated asks are dropped"
description: "A reviewer's pass notes under an Ask heading no longer become asks: an item with no proposed change goes to the packet's dropped_asks with a reason, and an ask that repeats an earlier one (same file and claim, or a plan-drift ask on a criterion a plan impact already names) is dropped as a repeat (shown in dropped_asks)."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T13:00:25-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_pass_notes_and_a_repeated_ask_leave_exactly_one_ask_and_show_as_dropped_asks"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_loop_findings.py`: the empty-section opening accepts "None new" and its forms, a plain lead-in line
ending in `:` opens a notes list (a bullet under it starts an ask only when it opens with a file:line or proposes a
change, ends in a question, carries a class tag, or opens with a plan-impact mark), and an Ask-section item with no change mark, no question and no tag is a pass note,
not an ask. `review_loop_findings.repeats_an_ask` is the repeated-ask rule; `review/review_loop_ruled.py` (new) files
a repeat under `dropped_asks` and the earlier ask stays unchanged;
`review_loop_packet.py` writes the dropped notes to `dropped_asks` with their reason.

## Evidence

judgment: a code reviewer's "None new." followed by a "Checks run (no defects found):" list became six asks, and a
test reviewer's ask repeated the AC2 plan-impact ask, so the user got seven rulings that asked nothing. Second report
of this class.

## Result

The new tests fail against master's scripts and pass. Over the real reviewer reports: parsed 281 of 317 (36 have no
findings layout), asks 99 before and 86 after, 13 pass notes dropped, no real ask lost.

## Watch

None: a parser fix with a fixed outcome.

## Back-out

Revert the commit.
