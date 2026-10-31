---
type: "Change"
change_type: "changed"
title: "The review status stops move to their own module"
description: "code_step's review status stops (tool fault, critical blocker, setup fault, unverified check, review cap) move from code_step_review.py to code_step_review_stops.py, with no change in what a run prints or saves."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T11:54:45-05:00"}
seq: 260
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_crashed_review_call_stops_as_a_tool_fault_not_as_a_blocker"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code/code_step_review_stops.py` holds `stop_on_review_status` and its helpers: `is_capped_review`,
`left_findings_open`, `review_stop_next_step`, `BLOCKER_STOP_TEXT`, `blocker_stop_next_step` and `ask_lines`. The stop
branches' bodies moved unchanged, except that the stops write through `set_stop`. The plan-impact branch moved to its
caller, `command_after_review`, ahead of the `stop_on_review_status` call, because it opens the plan-impact modal that
`code_step_review.py` defines. It still runs first, as before. `code_step_review.py` drops from 980 to 854 lines, so the next stop reason can land under the
1000-line rule.

## Evidence

A pure move by concern. The script rules refuse a new route in a script over 1000 lines.

## Result

No behavior change, so no test fails before it. The named test and the rest of the code-step suites pass before and
after the move.

## Watch

None; no behavior change.

## Back-out

Revert `code_step_review_stops.py`, the import lines in `code_step_review.py` and `code_step.py`, the plan-impact
branch in `command_after_review`, and the test list edits.
