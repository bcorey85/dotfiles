---
type: "Change"
change_type: "fixed"
title: "Review loop tags round-2 findings fix_induced by script"
description: "The scripted review loop sets fix_induced to yes or no on every located finding of round two or later, from the lines the earlier round's fix changed, with no model call, so the logs can tell fix-caused defects from ones round one missed."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-02T17:36:55-06:00"}
seq: 10
kind: "fix"
components: ["script/review-loop-script", "skill/review"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_fix_induced.py::FixInducedTagTest.test_a_round_two_finding_inside_a_fix_hunk_tags_yes"
asked: ""
proof: []
unmeasured: "The tag is a new column; the next intake can count yes against no on round-two rows, and no earlier reading exists to compare."
---

## Change

`lib/diff_ranges.py` reads a unified diff into the new-side line ranges it changes (added runs, and the line where a pure deletion sat; context lines are not changes) and tests whether a line is inside a range widened by `RANGE_SLACK` lines. `review/review_loop_fix_induced.py` reads `round<N-1>-fix.diff`, which the loop already writes after each fix, and returns the tag: the reviewer's own value when set, no tag in round one or for a finding with no file or line, else `yes` inside the changed lines and `no` outside. `review_loop_script.telemetry` adds `fix_induced=` to each finding row it logs.

## Evidence

Round one logs 1,088 findings and round two 526, but 8 of 1,614 rows carry `fix_induced` because the reviewer fills it by hand.

## Result

13 new tests pass; they fail without the change (no module, no key on the row).

## Watch

None. The next intake can read the share of `yes` among round-two rows.

## Back-out

Revert the commit: drop the two new modules and the three lines in `telemetry`.
