---
type: "Change"
title: "plan hook asks for a re-check after the last Edit while a renumber is in progress"
description: "When every plan parse failure is a kind a renumber passes through (duplicate id, missing section, section without status), the plan hook says the plan may be mid-edit and asks the session to re-check after the last Edit, and to report and stop only if the error is still there. A list with any other kind keeps the report-and-stop message."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T13:52:44-05:00"}
seq: 271
kind: "fix"
components: ["script/code-step", "script/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_plan_hook_on_a_duplicate_phase_id_asks_for_a_re_check_after_the_last_edit_and_no_stop"
asked: ""
proof: []
unmeasured: "Fires only while a session renumbers phase headings by hand; no intake number reads it."
---

## Change

The plan hook runs after each Edit of the plan file. When every parse failure is a renumber-transit kind (duplicate id, missing section, section without status), it now prints a message that says the plan may be mid-edit, for example renumbering headings one Edit at a time, and asks the session to re-check after the last Edit. It tells the session to report the lines and stop only if the error is still there then. A list that holds any other kind (unparsed line, moved without target, moved without deviation) keeps the old report-and-stop message. The start and resume paths keep it too.

## Evidence

Judgment from a work session that renumbered phase headings one Edit at a time. Each intermediate Edit left two headings with the same id and drew a stop order. The finished plan parsed cleanly.

## Result

A plan with two `Phase 2` headings gets the re-check message. The test fails before the change and passes after it. The existing plan-hook and plan-format tests still pass.

## Watch

None. No intake number reads this message.

## Back-out

Remove `plan_mid_edit_message` and `MID_EDIT_KINDS` from `plan_format.py` and the `MID_EDIT_KINDS` branch of `plan_write_failure` in `code_step_hooks.py`.
