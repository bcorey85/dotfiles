---
type: "Change"
change_type: "fixed"
title: "decide adopt on an applied plan impact clears the commit gate"
description: "`decide adopt` on a hand-back whose held impacts are all applied, with nothing else open, records the ruling and clears the gate with no new review loop; `code_wait.py review` lists each held impact of a clean packet and tells /code to defer them when the loop ends."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T02:32:03-06:00"}
seq: 2
kind: "fix"
components: ["script/review-fix", "script/code-wait"]
evidence: ["code-run-adopts-plan-impact-but-leaves-commit-gate"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_decide_adopt_on_an_applied_held_impact_settles_the_gate_with_no_review_loop"
asked: ""
proof: []
reverts: "2026-11-05-code-review-start-prints-the-defer-action-for-held"
unmeasured: ""
---

## Change

One predicate, `handback.adopt_settles`, decides it: every held impact carries `applied` and the packet carries no
findings. Both the packet-state path and the hand-back path use it, so an adopt that `adopt_settles` rejects
re-dispatches on the packet-state path and stops for `/code resume` on the hand-back path. When the ruling cannot clear the
commit gate, `decide` and `defer` print `stop` with the reason, not `done`. `code_wait.py review` prints a plan-impact
notice after the loop ends with a clean packet, listing each held impact and telling /code to defer them to phase end (`code_review_start.py` no longer prints a defer line).

## Evidence

A /code run adopted a plan impact whose fix was already in the tree, but `decide adopt` printed a stop and the commit
gate stayed dirty until another review loop ran.

## Result

New tests in `tests/scripts/test_review_fix_script.py` and `tests/scripts/test_code_wait.py`
(`WaitReviewTest::test_a_finished_review_lists_each_held_plan_impact_and_the_defer_sentence_and_not_an_adopted_one`).

## Watch

None.

## Back-out

Revert the commit.
