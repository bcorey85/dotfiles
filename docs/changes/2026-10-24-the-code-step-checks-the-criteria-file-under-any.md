---
type: "Change"
change_type: "fixed"
title: "The code step checks the criteria file under any Acceptance heading"
description: "The code step now stops on a missing or empty acceptance-criteria.md under any level 2 or 3 heading that starts with Acceptance, case-insensitive. Before, it stopped only when the plan held the exact line `## Acceptance Criteria`; any other wording skipped the check with no output."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T23:35:22-05:00"}
seq: 22
kind: "fix"
components: ["script/code-step", "script/plan-format"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_empty_criteria_file_stops_whatever_the_wording_of_the_criteria_heading"
asked: ""
proof: []
unmeasured: ""
---

## Change

`plan_format.ACCEPTANCE_HEADING` is `^#{2,3}\s+acceptance\b`, case-insensitive. `code_step.check_acceptance_criteria` uses it in place of the exact-line match.

## Evidence

A census of the agent-read toolkit scripts found that `### Acceptance criteria` or `## Acceptance` returned True silently. The coder was then dispatched with no criteria file.

## Result

The test covers three headings. It fails 3 of 3 subtests against the old script and passes after the fix.

## Watch

None. The stop shows in the session, and the `acceptance-stub` scan row counts it.

## Back-out

Revert the edits to `code_step.py` and `plan_format.py`.
