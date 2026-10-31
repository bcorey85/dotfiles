---
type: "Change"
change_type: "fixed"
title: "code skill reads say.md and question.md only when present"
description: "The code skill's hand-back step reads say.md and question.md only when each exists and is not empty."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T23:05:53-05:00"}
seq: 86
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_the_coder_wait_cap_stop_writes_question_md_with_the_restart"
asked: ""
proof: []
unmeasured: "Fork hand-back reads are not logged; no intake number reads them."
---

## Change

Step 3 of the code skill reads each hand-back file only when present and not empty, and the invoke-skill line names
`--finding`.

## Evidence

A code fork reported that the question.md the skill reads next does not exist; the script writes it only on a question.

## Result

The fork no longer looks for a file that a run without a question never writes.

## Watch

None.

## Back-out

Revert the commit.
