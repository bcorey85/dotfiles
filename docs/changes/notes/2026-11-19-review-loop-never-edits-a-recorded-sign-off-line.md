---
type: "Change"
change_type: "fixed"
title: "review loop never edits a recorded sign-off line"
description: "A coder pass that edits or deletes a sign-off line in a decision log, deviations list or evidence file gets the lost lines put back and an ask filed, and a reviewer finding against a ruling goes to ask with no fix dispatched."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 4
kind: "fix"
components: ["script/review-loop-script", "script/plan-format", "agent/code-reviewer"]
evidence: ["review-loop-rewrites-recorded-sign-offs-in-the"]
watches: []
test: "tests/scripts/test_review_loop_script.py::SignoffLinesLoopTest::test_a_coder_that_deletes_a_sign_off_in_a_plan_deviations_section_gets_the_file_put_back"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/plan_format.py` `signoff_lines` reads the sign-off lines of a decision log, a `## Plan Deviations` section or an
evidence file. The new `review/review_loop_signoffs.py` snapshots them before each coder pass; after the pass,
`lib/protected_lines.py` puts back only the lost lines into the current text, so an edit another session made during
the pass survives. A finding aimed at a sign-off line is filed as an ask naming the entry and never reaches the coder.

## Evidence

The review loop rewrote a recorded user sign-off in a decision log.

## Result

`SignoffLinesLoopTest` in `test_review_loop_script.py`, `test_protected_lines.py`, and the `signoff_lines` tests in
`test_plan_format.py`.

## Watch

None.

## Back-out

Revert the commit.
