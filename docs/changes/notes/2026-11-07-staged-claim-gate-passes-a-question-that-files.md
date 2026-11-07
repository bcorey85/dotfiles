---
type: "Change"
change_type: "fixed"
title: "Staged-claim Stop gate passes a question that files tickets"
description: "A closing question that files sub-tickets or subtasks, or files something in Jira, Linear or GitHub, is one to ask and passes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T01:28:20-06:00"}
seq: 2
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_a_question_about_prefixed_tickets_or_a_named_tracker_passes_but_a_local_step_is_sent_back"
asked: ""
proof: []
unmeasured: ""
---

## Change

`permission_question.OUTWARD_STEP` takes `sub-?tickets`, `sub-?tasks` and `sub-?issues` after file/open/create/raise, and a tracker name only after such a verb, a pronoun object and in/on/to/into. `Want me to rerun the tests?`, `make the lookup linear?` and `open the task file?` still block.

## Evidence

judgment: the gate blocked "Want me to file the per-domain sub-tickets?", an outward step. The new test fails on the base commit and passes after.

## Result

Median run time over 21 runs: staged_claim_gate 30 ms against a bare Python start of 8 ms.

## Watch

—

## Back-out

Revert the commit's hunks in the named files.

