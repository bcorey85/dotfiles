---
type: "Change"
title: "A coder escalates to /eng-spec only through a marker line"
description: "code_step stops a run for /eng-spec only on a `RECOMMEND: eng-spec` line, so a coder report that says no /eng-spec is needed goes on to review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T23:40:00-05:00"}
seq: 135
kind: "fix"
components: ["script/code-step", "skill/coder-core"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_coder_report_that_only_mentions_eng_spec_goes_on_to_review"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_report.recommends_eng_spec` reads one marker line, `RECOMMEND: eng-spec`. `unreviewable_outcome` routes
  on it and no longer on any `/eng-spec` in the report.
- The coder briefs (plan phase, planless task and asks round) name that line. They take the text from
  `ENG_SPEC_MARKER` in `code_step_report`.
- `coder-core` tells the coder to end with that line to escalate, and never to write it otherwise.

## Evidence

- A /code run finished its edits. The coder wrote "so no /eng-spec is needed". code_step read that as an escalation
  and stopped before review.
- The new test fails on the old script.

## Result

- A coder report that mentions /eng-spec in free text goes on to review.

## Watch

—

## Back-out

Revert the commit.
