---
type: "Change"
change_type: "fixed"
title: "Asks-done removes a stale run-folder fix-findings file"
description: "The fix run that asks-done prints now deletes a fix-findings.md an earlier run left in the run folder, so a failed new Write cannot make the launch read old findings."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-19T01:09:56-06:00"}
seq: 3
kind: "fix"
components: ["script/review-fix", "script/review-launch"]
evidence: ["tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_asks_done_removes_a_stale_run_folder_findings_file_and_says_so"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_asks_done_removes_a_stale_run_folder_findings_file_and_says_so"
---

## Change

`command_asks_done` calls `review_launch.remove_stale_run_folder_findings` on the first print of the fix run, before it prints the redispatch or no-launch-record text; `asks-done --correct` keeps the file. The launch deletes run-folder inputs only after it succeeds, so an earlier run's `fix-findings.md` stayed and a failed Write of the new one left the launch reading it. The asks findings file is never touched.

## Evidence

tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_asks_done_removes_a_stale_run_folder_findings_file_and_says_so

## Result

An older run-folder `fix-findings.md` is gone before the session writes deferred findings, and the output says it was removed.

## Watch

—

## Back-out

Revert the call in `command_asks_done` and `remove_stale_run_folder_findings` in `review_launch.py`.
