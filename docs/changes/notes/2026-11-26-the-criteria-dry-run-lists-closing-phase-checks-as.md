---
type: "Change"
change_type: "fixed"
title: "The criteria dry run lists closing-phase checks as CLOSING"
description: "criteria_dry_run.py prints `CHECK <label> CLOSING <skill> <command or item text>` for each Automated Verification item of a closing phase and runs none of them, so every phase's checks show in the report; the exit code is unchanged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:06:41-06:00"}
seq: 6
kind: "fix"
components: ["script/criteria-dry-run", "skill/eng-spec"]
evidence: ["tests/scripts/test_criteria_dry_run.py"]
watches: []
test: "tests/scripts/test_criteria_dry_run.py::ClosingPhaseTest.test_a_closing_phase_item_is_listed_as_closing_and_not_run"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`criteria_in_plan` returns a closing phase's items with the skill its title names; `dry_run` prints them as CLOSING lines and does not run them. They take numbers in the plan-wide sequence. `skills/eng-spec/phases/6-finalize.md` names the CLOSING label. This replaces the 2026-10-26 change that gave them no line.

## Evidence

A bench plan's `Phase 4: Close pass` held six checks; the dry-run report ended at Phase 3 with no sign they exist, and the session filed it as a defect. The test fails on the old tree (no CLOSING line) and passes after.

## Result

A planner sees every phase's checks and which skill runs the closing ones.

## Watch

—

## Back-out

Restore the `continue` on `closing_skill` in `criteria_in_plan`, drop the CLOSING print, and revert the test and the 6-finalize.md line.
