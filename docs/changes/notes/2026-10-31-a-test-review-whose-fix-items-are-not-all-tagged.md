---
type: "Change"
change_type: "fixed"
title: "A test review whose fix items are not all tagged goes to the disposition call"
description: "A reviewer's fix item always reaches the coder: a reply the tagged-bullet parse cannot fully account for now goes to the disposition call instead of losing the items it skipped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T15:15:30-05:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_reply_of_bold_head_items_with_a_tagged_sub_bullet_falls_back_to_the_disposition_call"
asked: ""
proof: []
unmeasured: ""
---

## Change

`parse_tagged_bullets` in `scripts/review/review_loop_findings.py` used to trust any reply holding one `fix:`/`ask:`/`nit:` bullet, so the disposition call was skipped and every untagged item was dropped with no trace. It now returns None, and the disposition call reads the reply, when `tagged_bullets_leave_items_out` finds any of: a tagged bullet nested deeper than the shallowest list marker; an untagged line that opens with a bold head (a `**Label**:` report field is exempt); an untagged top-level item that names a file:line; or a stray disposition tag (`` `fix` ``, `(fix)`, `**fix**`) on a line the parse did not take. A reply of flat tagged bullets only still parses with no model call.

## Evidence

On one bench run the test reviewer wrote two fix items as bold heads. The second had a sub-bullet starting `Fix:`, which matched; the first, which named 19 of 21 checks as untested, was dropped, and the run ended at 8 of 44 constraints.

## Result

The named test, built on that reply shape, fails before the change and passes after. Tests for each of the four fallback rules and a script-level test pass, with the flat-bullet case still parsed directly. Targeted suite: `test_review_loop_script` passes; ruff is clean on the changed file.

## Watch

None.

## Back-out

Remove the `tagged_bullets_leave_items_out` call from `parse_tagged_bullets`.
