---
type: "Change"
change_type: "fixed"
title: "Permission-question Stop hook lets asks before irreversible app actions through"
description: "permission_question.OUTWARD_STEP names void, cancel, refund, revoke, submit, approve, archive, remove, overwrite, wipe, purge, truncate and destroy, so the Stop hook no longer sends back an ask before such a step."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T01:35:49-06:00"}
seq: 7
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_question_about_an_irreversible_step_in_an_external_app_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`OUTWARD_STEP` and the module docstring gain thirteen verbs for steps that do not undo in an external app or on disk.

## Evidence

judgment: the hook sent back an ask to void a record in a web app, a step the safety rules say to ask before. The new test fails on the base commit and passes after.

## Result

`test_staged_claim_gate.py` 45 of 45 pass; lint clean.

## Watch

—

## Back-out

Remove the thirteen verbs from `OUTWARD_STEP` and the docstring, and the new test.
