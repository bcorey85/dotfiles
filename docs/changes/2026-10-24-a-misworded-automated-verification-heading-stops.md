---
type: "Change"
change_type: "fixed"
title: "A misworded Automated Verification heading stops the code step"
description: "The code step now stops, with the file line, at a level 4 heading that holds automated and verif but is not the exact `#### Automated Verification` heading, at start, at the plan check and at a plan edit during a /code run. Before, plan_format read a phase's verification commands only under the exact heading, so a misworded one counted as no commands and the phase closed green with nothing run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T23:35:22-05:00"}
seq: 23
kind: "fix"
components: ["script/plan-format", "script/code-step"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_plan_format.py::AutomatedVerificationRowsTest::test_a_misworded_verification_heading_raises_with_its_file_line_and_the_expected_heading"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `automated_verification_rows(lines, name, first_line, strict=True)` raises `PlanFormatError` for such a heading. The message names the file line and the expected heading. A `Manual Verification` heading does not raise.
- Only the start check, the plan check and the plan-write hook pass `strict`. The message names both fixes: `#### Automated Verification:` for commands, or `#### Manual Verification:` for human checks. The gate env, the close-time readers and verify-prep keep the non-raising read, so an old plan elsewhere in the repo does not stop a dispatch.
- `code_step_boundary.verification_format_failure` passes the plan name and line, and puts the error in its stop message.

## Evidence

A census of the agent-read toolkit scripts found this path. The done line said "The phase lists no verification commands", which is the same line a phase with no commands prints.

## Result

The plan_format test and `test_code_step.py::CodeStepTest::test_plan_check_fails_a_misworded_automated_verification_heading_with_its_line` fail before the fix and pass after it. A guard test shows that other level 4 headings do not raise.

## Watch

None. The stop shows in the session, and no intake stream counts it.

## Back-out

Revert the edits to `plan_format.py` and `code_step_boundary.py`.
