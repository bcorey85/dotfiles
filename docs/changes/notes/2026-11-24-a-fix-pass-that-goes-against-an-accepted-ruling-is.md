---
type: "Change"
change_type: "changed"
title: "A fix pass that goes against an accepted ruling is put back"
description: "After each fix pass of a run that holds a ruling, a ruling-check model call judges the pass against the rulings; a pass found against one has its work tree and index restored (a coder commit stays, named) and the run stops critical-blocker with against_ruling in the packet."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T19:40:45-06:00"}
seq: 6
kind: "fix"
components: ["script/review-loop-script", "script/handback"]
evidence: ["tests/scripts/test_review_loop_script.py", "tests/scripts/test_handback.py"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_pass_that_keeps_what_a_ruling_dropped_is_put_back_and_stops_the_run"
asked: ""
proof: []
unmeasured: "No rule-meter run applies: the change is script code, not a skill or agent rule."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_loop_ruling_check.py` copies every file a fix pass may write, except held files that have a holder row, then judges the pass diff against the run's accepted rulings with one `ruling-check` call. On an `against` verdict it restores the work tree and index (a commit the coder made stays in HEAD and the blocker names it), deletes the files the pass created, keeps the findings open and stops the run `critical-blocker`, naming the file and the ruling. The packet gains `against_ruling` and `handback.py` reads it. A judge reply that does not parse stops the run as a tool fault and leaves the pass in place.

## Evidence

`test_review_loop_script.py` pins the put-back (a second file inside the pass scope too), a kept verdict, a run with no ruling and an unparseable reply. `test_handback.py` pins the new packet key.

## Result

Before, a fix pass that kept code an accepted ruling dropped moved on to the next reviewer round.

## Watch

—

## Back-out

Revert the commit.
