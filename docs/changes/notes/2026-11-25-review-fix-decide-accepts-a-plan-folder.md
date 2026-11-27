---
type: "Change"
change_type: "fixed"
title: "review_fix decide accepts a plan folder"
description: "`review_fix.py decide --plan <plan folder>` records the Plan Deviations entry in the folder's plan file instead of crashing with IsADirectoryError; a folder with no plan file is a usage error that stores no ruling."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:20:30-06:00"}
seq: 4
kind: "fix"
components: ["script/review-fix", "script/plan-format"]
evidence: ["tests/scripts/test_review_fix_script.py", "tests/scripts/test_plan_format.py"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest.test_a_user_ruling_with_a_plan_folder_records_the_deviation_in_that_folders_plan_file"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`plan_format.append_deviation` resolves its path through `plan_file_of`, so a plan folder writes to the plan file inside it. `review_fix.py decide` resolves `--plan` the same way before any write; a folder with no plan file exits 2 with the `PlanFormatError` text and records no ruling. The `Recorded in` line names the plan file.

## Evidence

`test_plan_format.py` pins a folder with `plan.md` getting the entry and an empty folder raising. `test_review_fix_script.py` pins `decide keep --by user --plan <folder>` writing the entry into that folder's `plan.md`, and an empty or ticket-only folder exiting 2 with no ruling stored.

## Result

Before, `decide --plan <folder>` crashed after the ruling rows were written; now it records the deviation in the folder's plan file.

## Watch

—

## Back-out

Revert the `plan_file_of` line in `append_deviation` and the `--plan` resolve block in `review_fix.command_decide`.
