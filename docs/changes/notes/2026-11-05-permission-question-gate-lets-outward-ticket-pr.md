---
type: "Change"
change_type: "fixed"
title: "Permission-question gate lets outward ticket, PR and message questions through"
description: "The Stop gate's permission-question check counts filing a ticket, issue or PR, replying, notifying, messaging, pinging and Slack as outward steps, so a closing question about them is no longer sent back."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T16:49:36-06:00"}
seq: 9
kind: "fix"
components: ["script/permission-question"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_question_about_filing_a_ticket_or_messaging_someone_passes"
asked: ""
proof: []
unmeasured: ""
---

## Change

`gates/permission_question.py` `OUTWARD_STEP` adds reply, notify, message and ping, a `file|open|create|raise` + up to two words + `ticket|issue|pull request|PR|MR` arm, and `slack`.

## Evidence

judgment: a work session asked before filing a ticket and before a Slack message; the gate sent both back as permission questions, though each leaves the machine. The new test's five messages fail on the base commit and pass after; a local "fix the ticket reference" question is still sent back.

## Result

`test_staged_claim_gate.py` 47 pass; lint clean.

## Watch

—

## Back-out

Revert the `OUTWARD_STEP` additions and the two tests.
