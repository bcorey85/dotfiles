---
type: "Change"
change_type: "fixed"
title: "an adopted plan impact reaches the resume round's fix coder"
description: "A resume that adopts a plan impact puts it in that round's fix-coder list before any test or reviewer runs, and a coder that skips it or leaves no diff ends the round with a blocker naming the ruling and no reviewer."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:13-06:00"}
seq: 12
kind: "fix"
components: ["script/review-fix", "script/review-loop-script"]
evidence: ["review-resume-records-an-adopted-plan-impact-but"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_a_real_decide_adopt_sends_the_adopted_finding_to_the_resume_rounds_fix_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_fix.py` `write_ruling_entry` passes the decision, owner and ruling time to
`handback_store.record_ruled_impact`. `review/review_user_ruled.py` marks the adopted finding and sends it to the fix
coder first. `review_loop_ruled.py` fails the round when an adopted ruling produced no fix diff, and records an
applied one as applied.

## Evidence

A resume recorded the adopted plan impact but no coder ever applied it.

## Result

Adopted-ruling tests in `test_review_user_ruled.py`, `test_review_loop_ruled.py` and `test_review_fix_script.py`.

## Watch

None.

## Back-out

Revert the commit.
