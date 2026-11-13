---
type: "Change"
change_type: "fixed"
title: "Permission gate passes a closing question that names an outside destination"
description: "The Stop hook's permission-question check lets a closing question through when it names a destination outside the machine (a PR, issue, ticket, thread, GitHub, a #number) or says public."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T11:45:24-06:00"}
seq: 1
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_question_naming_an_outside_destination_passes_but_a_local_step_is_sent_back"
asked: ""
proof: []
unmeasured: ""
---

## Change

`gates/permission_question.py` `OUTWARD_STEP` gains `public`/`publicly` and an outside destination after `to`, `on`,
`in` or `off` (PR, MR, pull request, merge request, issue, ticket, thread, Jira, upstream, `#<number>`; GitHub,
GitLab and Linear after `to`, `in` or `off` only). The search skips the question's opening phrase, so the `to` of
`want me to` is no destination.

## Evidence

judgment: the gate blocked a closing question about posting a public PR comment (2026-11-11), the third sighting of
the class. A sweep of local transcripts found two more blocked questions that named an outside destination
("add your data to vkd3d-proton #3304?", "that name off GitHub?").

## Result

The new test fails on the old tree and passes; the full suite passed (3769 tests, 0 failed).

## Watch

None: a fixed pattern.

## Back-out

Revert the commit.
