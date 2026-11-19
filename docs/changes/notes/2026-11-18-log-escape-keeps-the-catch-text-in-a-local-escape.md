---
type: "Change"
change_type: "fixed"
title: "log-escape keeps the catch text in a local escape-text file"
description: "A logged escape now keeps its one-line catch text on the machine that caught it, so a hand catch can be read back by cause."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-18T11:28:49-06:00"}
seq: 1
kind: "fix"
components: ["script/log-escape", "script/ledger-write"]
evidence: ["tests/scripts/test_log_escape.py", "tests/scripts/test_ledger_write.py"]
watches: []
test: "tests/scripts/test_log_escape.py::LogEscapeTest.test_desc_row_lands_in_the_text_file_and_not_in_the_ledger_payload"
---

## Change

`log-escape` appends a row with the catch text (`desc`) and every other field of the escape row except `scan_flagged` to `~/.claude/escape-text.jsonl` when `desc` is not empty. The ledger row still carries no `desc`. Before, the text was dropped and a hand catch recorded no cause. The row is written only when `stage_found` is a stage where the user caught the defect (`cc`, `walkthrough`, `pr-human`, `peer-review`, `prod`, `other`); any other stage writes no text row. `ledger-write` now keeps `desc`, `file`, `commit`, `branch` and `ticket` as strings in every local fallback row, so a ticket such as "0123" is no longer stored as 123. `log-escape` now refuses a `stage_found` outside its list (exit 1), because the ledger would store a typo as `other`, a hand-catch stage; before, such a call logged without error.

## Evidence

tests/scripts/test_log_escape.py
tests/scripts/test_ledger_write.py

## Result

A hand catch's text reads back on the machine that caught it.

## Watch

—

## Back-out

Remove the `append_escape_text` function, its call and the `hand_catch_stages` variable from `log-escape`, restore the `desc` and `file` header text there and the `desc` line in `escape/SKILL.md` to "never stored", remove the `escape_text` case arm from `ledger-write`, and remove the `escape_text` mentions in its header (the row-type list and the file-table row). Remove the `stage_found` list check from `log-escape`, restore its header to fold `stage_found` silently, and drop the header sentences that say a stage is refused or must be on a list, and the hand-catch stderr sentence. Restore the string-key comment and the key list in the `typed` function of `ledger-write` to the keys it listed before (without `desc`, `file`, `commit`, `branch`, `ticket`). Delete the tests that assert the text rows and the stage refusal: the text-file tests, `test_a_stage_found_outside_the_list_is_refused_and_writes_no_row` and `test_check_refuses_a_stage_found_outside_the_list` in `test_log_escape.py`, and `test_local_escape_text_row_types_line_and_keeps_text_fields_as_strings`, `test_a_ticket_with_a_leading_zero_stays_a_string` and `test_file_commit_branch_and_desc_stay_strings_in_a_review_escape_row` in `test_ledger_write.py`.
