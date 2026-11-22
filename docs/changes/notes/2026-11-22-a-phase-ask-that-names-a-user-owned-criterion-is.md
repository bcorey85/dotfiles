---
type: "Change"
change_type: "fixed"
title: "A phase ask that names a user-owned criterion is held for the user"
description: "phase_asks opens a reviewer ask that names a user-owned acceptance criterion as user-only, so the session cannot rule it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T13:35:58-06:00"}
seq: 27
kind: "fix"
components: ["script/phase-asks", "script/code-review-start"]
evidence: ["a-reviewer-question-that-changes-a-criterion-is"]
watches: []
test: "tests/scripts/test_phase_asks.py::CriterionAskTest::test_an_ask_naming_a_user_owned_criterion_opens_user_only_with_the_ids"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_review_start.py` records the plan path. `phase_asks.record_open` marks an ask user-only when it names a criterion id the plan's criteria file holds and the owner is `user`. `phase_asks list` names the ids and the next step.

## Evidence

/code makes the session rule each reviewer question. A question whose answer changes a user's criterion had no way to wait for the user.

## Result

CriterionAskTest in `test_phase_asks.py`.

## Watch

None.

## Back-out

Revert the commit.
