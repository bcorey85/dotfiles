---
type: "Change"
change_type: "changed"
title: "Coder open questions come back as a JSON list"
description: "The coder names its open questions on one OPEN QUESTIONS JSON-list line, and /code reads only that line, so a question that contains no or none reaches the router instead of being dropped."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T00:09:12-05:00"}
seq: 307
kind: "fix"
components: ["skill/coder-core", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_an_open_question_containing_no_stops_an_asks_coder_that_changed_nothing"
asked: ""
proof: []
unmeasured: ""
---

## Change

- coder-core's review handoff gains `OPEN QUESTIONS: <JSON list of strings>`, or `[]` for none.
- `code_step_report.open_questions` reads that one line and returns its strings. `none` or no line means none. A
  value that is not a JSON list of strings comes back as one flagged item that quotes it, never dropped.
- `coder_flags` is deleted, with its free-text scan for "ambiguous" or "open question" that dropped any line holding
  "no" or "none". Its two callers in `code_step.py` call `open_questions`.

## Evidence

Read of `coder_flags`: "Open question: no test covers the refund path" matched its "no" filter and vanished.

## Result

A question that contains "no" now stops an asks coder that changed nothing; a malformed line is flagged. Tests pin
both. Targeted tests pass.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit.
