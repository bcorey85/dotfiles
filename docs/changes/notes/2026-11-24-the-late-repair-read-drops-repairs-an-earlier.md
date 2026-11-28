---
type: "Change"
change_type: "fixed"
title: "The late repair read drops repairs an earlier review round already read"
description: "The review loop clears its list of repair passes at the start of each review round, so a converged run reads only the repairs made after the last review round."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T16:38:52-06:00"}
seq: 4
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::FixRoundWiringTest::test_a_repair_before_a_later_review_round_is_dropped_from_late_repairs"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

Every gate, lint, class-closure or stale-prose repair that changed code was kept for the final late-repair read and
never cleared, so a converged run re-read a lint diff from round one that a later round had already reviewed. The loop
now empties the list as each review round begins. A lint repair made after a fix pass is put into that round's fix
diff and its second-round plan, so the next round reads it before the list is emptied. A lint repair after the last
fix pass of the round budget is still read at the end.

## Evidence

Judgment from a code read of the walk and the late-repair list.

## Result

The new test fails on the old walk (the list still holds the earlier repair at the second round) and passes now. The
existing test that a lint repair after a fix round stays in the list still passes.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
